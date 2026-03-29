/**
 * Generates the API injection script for widget iframes.
 *
 * This script is injected into <head> of every widget HTML before rendering in an iframe.
 * It provides:
 * - window.fetchContentData() — fetches data from the ContentNode API
 * - window.getTable() — convenience helper to get a specific table
 * - window.startAutoRefresh() / window.stopAutoRefresh() — auto-refresh support
 * - window.onerror / unhandledrejection — visual error display instead of blank screen
 * - API_BASE origin resolution that works in about:blank iframe contexts
 */
export function buildWidgetApiScript(params: {
    contentNodeId: string
    authToken: string
    autoRefresh: boolean
    refreshInterval: number // in ms
    /** ID виджета (node.id / item.id) — для стека и pushCurrentDataToStack */
    widgetId?: string
    activeFilters?: string // URL-encoded FilterExpression JSON
    precomputedTables?: any[] // Pipeline-computed tables (bypass API call)
    /** Стек предыдущих датасетов для виджета-инициатора (только если виджет инициировал фильтр) */
    dataStack?: Array<{ tables: any[] }>
    /** Отфильтрованные таблицы (подмножество строк по активным фильтрам) — виджет сопоставляет с полными данными и определяет выделение без activeFilters */
    filteredTablesForHighlight?: Array<{ name: string; columns?: any[]; rows: any[] }>
}): string {
    const { contentNodeId, authToken, autoRefresh, refreshInterval, widgetId, activeFilters, precomputedTables, dataStack, filteredTablesForHighlight } = params

    // Safely escape the filters string for embedding in JS
    const filtersLiteral = activeFilters ? `'${activeFilters.replace(/'/g, "\\'")}'` : 'null'
    const precomputedLiteral = precomputedTables ? JSON.stringify(precomputedTables) : 'null'
    const dataStackLiteral = dataStack && dataStack.length > 0 ? JSON.stringify(dataStack) : '[]'
    const filteredDictLiteral =
        filteredTablesForHighlight && filteredTablesForHighlight.length > 0
            ? JSON.stringify(Object.fromEntries(filteredTablesForHighlight.map((t) => [t.name, t])))
            : '{}'

    return `
        <script>
            // API Client for dynamic data access (injected by GigaBoard)
            window.CONTENT_NODE_ID = '${contentNodeId}';
            window.AUTH_TOKEN = '${authToken}';
            window.WIDGET_ID = ${widgetId != null ? `'${String(widgetId).replace(/'/g, "\\'")}'` : 'null'};
            window.__PRECOMPUTED_TABLES = ${precomputedLiteral};
            window.__DATA_STACK = ${dataStackLiteral};
            // Resolve API_BASE: about:blank iframes may have "null" origin
            window.API_BASE = (function() {
                var origin = window.location.origin;
                if (origin && origin !== 'null') return origin;
                // Fallback: try ancestorOrigins (Chrome) or parent origin
                try {
                    if (window.location.ancestorOrigins && window.location.ancestorOrigins.length > 0) {
                        return window.location.ancestorOrigins[0];
                    }
                    if (window.parent && window.parent.location.origin) {
                        return window.parent.location.origin;
                    }
                } catch(e) {}
                return 'http://localhost:5173';
            })();
            window.AUTO_REFRESH_ENABLED = ${autoRefresh};
            window.REFRESH_INTERVAL = ${refreshInterval};

            // Cross-filter: active filters (URL-encoded JSON or null)
            window.ACTIVE_FILTERS = ${filtersLiteral};
            // Отфильтрованные таблицы по имени — виджет сравнивает с полными данными и определяет выделение (строка в full есть в filtered => выделена)
            window.__FILTERED_TABLES_DICT = ${filteredDictLiteral};
            window.__isRowHighlighted = function(tableName, dimCol, value) {
                var ft = window.__FILTERED_TABLES_DICT && window.__FILTERED_TABLES_DICT[tableName];
                return !!(ft && ft.rows && ft.rows.some(function(r) { return r[dimCol] == value; }));
            };

            // Global error handler — show errors visually instead of blank screen
            window.onerror = function(msg, src, line) {
                // Chromium quirk: RO callback + layout in same turn; not a real failure (см. gigaboardEchartsIframeGuard ResizeObserver)
                if (typeof msg === 'string' && msg.indexOf('ResizeObserver loop') !== -1) {
                    return true;
                }
                console.error('Widget error:', msg, 'at', src, 'line', line);
                var el = document.getElementById('chart') || document.body;
                if (el) {
                    el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#ef4444;font-family:sans-serif;font-size:13px;padding:16px;text-align:center;">Ошибка: ' + msg + '</div>';
                }
            };
            window.addEventListener('unhandledrejection', function(e) {
                console.error('Widget unhandled rejection:', e.reason);
            });

            window.fetchContentData = async function() {
                // Pipeline snapshot: не-null массив с данными — без сетевого запроса
                if (window.__PRECOMPUTED_TABLES != null && window.__PRECOMPUTED_TABLES.length > 0) {
                    return {
                        tables: window.__PRECOMPUTED_TABLES,
                        text: '',
                        metadata: {}
                    };
                }
                // Явно пустой снимок от compute-filtered (например, фильтр отсёк все строки)
                if (Array.isArray(window.__PRECOMPUTED_TABLES) && window.__PRECOMPUTED_TABLES.length === 0) {
                    return { tables: [], text: '', metadata: {} };
                }
                // Сетевой путь: временные сбои (429, сеть, cold start) раньше сразу давали пустые tables —
                // виджет показывал «нет данных» до ручного обновления. Несколько попыток с задержкой.
                var maxAttempts = 3;
                var lastErr = null;
                for (var attempt = 0; attempt < maxAttempts; attempt++) {
                    try {
                        if (attempt > 0) {
                            await new Promise(function(r) { setTimeout(r, 120 * attempt); });
                        }
                        var url = window.API_BASE + '/api/v1/content-nodes/' + window.CONTENT_NODE_ID;
                        if (window.ACTIVE_FILTERS) {
                            url += '?filters=' + window.ACTIVE_FILTERS;
                        }
                        var response = await fetch(url, {
                            headers: {
                                'Authorization': 'Bearer ' + window.AUTH_TOKEN,
                                'Content-Type': 'application/json'
                            }
                        });
                        if (!response.ok) throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                        var contentNode = await response.json();
                        return {
                            tables: (contentNode.content && contentNode.content.tables) ? contentNode.content.tables : [],
                            text: (contentNode.content && contentNode.content.text) ? contentNode.content.text : '',
                            metadata: contentNode.metadata || {}
                        };
                    } catch (error) {
                        lastErr = error;
                        console.error('Error fetching content data (attempt ' + (attempt + 1) + '/' + maxAttempts + '):', error);
                    }
                }
                console.error('Error fetching content data:', lastErr);
                return { tables: [], text: '', metadata: {} };
            };

            window.getTable = async function(nameOrIndex) {
                const data = await window.fetchContentData();
                if (typeof nameOrIndex === 'number') return data.tables[nameOrIndex];
                return data.tables.find(function(t) { return t.name === nameOrIndex; });
            };

            // ── Data stack (оснастка: стек ведёт хост, виджет только читает) ─────────────────
            // При добавлении фильтра хост кладёт текущий датасет в стек; при снятии — удаляет запись.
            // fetchStoredDataStack() возвращает весь накопленный стек [{ tables }, ...].
            window.fetchStoredDataStack = function() {
                return Array.isArray(window.__DATA_STACK) ? window.__DATA_STACK.slice() : [];
            };
            window.getDataStack = function() { return window.fetchStoredDataStack(); };
            window.getPreviousData = function() {
                var s = window.fetchStoredDataStack();
                if (!s.length) return null;
                var last = s[s.length - 1];
                return last && last.tables ? { tables: last.tables, text: '', metadata: {} } : null;
            };

            /**
             * Перед вызовом toggleFilter в обработчике клика вызови pushCurrentDataToStack() —
             * текущие (исходные) данные виджета попадут в стек; после обновления getPreviousData() вернёт их.
             */
            window.pushCurrentDataToStack = function() {
                var arr = window.__CURRENT_RENDER_TABLES;
                if (!arr || !Array.isArray(arr) || arr.length === 0 || !window.WIDGET_ID) return;
                try {
                    window.parent.postMessage({
                        type: 'widget:pushDataStack',
                        payload: {
                            widgetId: window.WIDGET_ID,
                            contentNodeId: window.CONTENT_NODE_ID,
                            tables: arr
                        }
                    }, '*');
                } catch(e) { console.error('pushCurrentDataToStack error:', e); }
            };

            // ── Cross-filter API ──────────────────────────────────────
            // All filter functions communicate with the parent frame via postMessage.
            // The parent (WidgetNodeCard / DashboardItemRenderer) listens and
            // dispatches to filterStore.

            /**
             * addFilter(...) overloads:
             * 1) addFilter(dimension, value) — legacy helper for simple equality.
             * 2) addFilter(filterExpressionObject) — set full cross-filter expression.
             *    Supports both simple condition and nested and/or groups.
             */
            window.addFilter = function(dimensionOrExpression, value) {
                try {
                    var isExpressionObject =
                        dimensionOrExpression &&
                        typeof dimensionOrExpression === 'object' &&
                        typeof dimensionOrExpression.type === 'string';

                    if (isExpressionObject) {
                        window.parent.postMessage({
                            type: 'widget:setFilterExpression',
                            payload: {
                                filter: dimensionOrExpression,
                                contentNodeId: window.CONTENT_NODE_ID
                            }
                        }, '*');
                        return;
                    }

                    window.parent.postMessage({
                        type: 'widget:addFilter',
                        payload: { dimension: dimensionOrExpression, value: value, contentNodeId: window.CONTENT_NODE_ID }
                    }, '*');
                } catch(e) { console.error('addFilter error:', e); }
            };

            /**
             * removeFilter(dimension) — remove filter for a specific dimension.
             * @param {string} dimension - Dimension name to remove
             */
            window.removeFilter = function(dimension) {
                try {
                    window.parent.postMessage({
                        type: 'widget:removeFilter',
                        payload: { dimension: dimension, contentNodeId: window.CONTENT_NODE_ID }
                    }, '*');
                } catch(e) { console.error('removeFilter error:', e); }
            };

            /**
             * toggleFilter(dimension, value) — toggle: if this exact filter
             * is already active, remove it; otherwise, set it.
             * Перед отправкой текущие данные виджета кладутся в стек (pushCurrentDataToStack).
             */
            window.toggleFilter = function(dimension, value) {
                try {
                    if (typeof window.pushCurrentDataToStack === 'function') window.pushCurrentDataToStack();
                    window.parent.postMessage({
                        type: 'widget:toggleFilter',
                        payload: { dimension: dimension, value: value, contentNodeId: window.CONTENT_NODE_ID }
                    }, '*');
                } catch(e) { console.error('toggleFilter error:', e); }
            };

            /**
             * getActiveFilters() — returns the currently active filters object (or null).
             * Useful for highlighting active selections in the widget.
             */
            window.getActiveFilters = function() {
                if (!window.ACTIVE_FILTERS) return null;
                try { return JSON.parse(decodeURIComponent(window.ACTIVE_FILTERS)); }
                catch(e) { return null; }
            };

            /**
             * isFilterActive(dimension, value) — check if a specific filter is set.
             * @returns {boolean}
             */
            window.isFilterActive = function(dimension, value) {
                var filters = window.getActiveFilters();
                if (!filters) return false;
                function check(expr) {
                    if (!expr) return false;
                    if (expr.type === 'condition') return expr.dim === dimension && (expr.value == value || String(expr.value) === String(value));
                    if (expr.type === 'and' || expr.type === 'or') {
                        return (expr.conditions || []).some(check);
                    }
                    return false;
                }
                return check(filters);
            };

            // Backward-compatible alias
            window.emitClick = function(field, value, metadata) {
                window.addFilter(field, value);
            };

            // Listen for filter/stack updates pushed from the parent
            window.addEventListener('message', function(event) {
                if (!event.data) return;
                if (event.data.type === 'filters:update') {
                    window.ACTIVE_FILTERS = event.data.filters || null;
                    if (typeof window._onFiltersChanged === 'function') {
                        window._onFiltersChanged();
                    }
                }
                if (event.data.type === 'widget:dataStack') {
                    window.__DATA_STACK = Array.isArray(event.data.stack) ? event.data.stack : [];
                }
            });

            window.startAutoRefresh = function(callback, intervalMs) {
                if (!window.AUTO_REFRESH_ENABLED) {
                    console.log('Auto-refresh disabled');
                    return null;
                }
                var interval = intervalMs || window.REFRESH_INTERVAL || 5000;
                return setInterval(async function() {
                    try {
                        var data = await window.fetchContentData();
                        callback(data);
                    } catch(e) { console.error('Auto-refresh error:', e); }
                }, interval);
            };

            window.stopAutoRefresh = function(intervalId) {
                if (intervalId) clearInterval(intervalId);
            };

            // ECharts в about:srcdoc: при движении по доске iframe временно 0×0 — ZRender всё равно крутит rAF и падает в drawImage.
            // 1) Не шлём window.resize. 2) resize() только при ненулевом getDom(). 3) Патч drawImage для нулевого canvas (только iframe).
            (function gigaboardEchartsIframeGuard() {
                try {
                    if (typeof CanvasRenderingContext2D !== 'undefined' && !CanvasRenderingContext2D.prototype.__gigaboardDrawImagePatched) {
                        CanvasRenderingContext2D.prototype.__gigaboardDrawImagePatched = true;
                        var _drawImage = CanvasRenderingContext2D.prototype.drawImage;
                        CanvasRenderingContext2D.prototype.drawImage = function() {
                            var img = arguments[0];
                            try {
                                if (img && typeof (img).width === 'number' && typeof (img).height === 'number' && img.width === 0 && img.height === 0) {
                                    return;
                                }
                            } catch (e) {}
                            return _drawImage.apply(this, arguments);
                        };
                    }
                } catch (e) {}

                var resizeTimer = null;
                var RO_DEBOUNCE_MS = 120;

                function domOk(el) {
                    if (!el || el.nodeType !== 1) return false;
                    return el.clientWidth > 0 && el.clientHeight > 0;
                }

                function wrapChartResize(inst) {
                    if (!inst || inst.__gigaboardResizeWrapped) return inst;
                    inst.__gigaboardResizeWrapped = true;
                    var origResize = inst.resize;
                    inst.resize = function(opts) {
                        var dom = inst.getDom && inst.getDom();
                        if (!domOk(dom)) return;
                        try {
                            return origResize.apply(this, arguments);
                        } catch (err) {
                            console.warn('echarts.resize skipped:', err && err.message);
                        }
                    };
                    return inst;
                }

                function gigaboardResizeAllCharts() {
                    if (resizeTimer) return;
                    resizeTimer = setTimeout(function() {
                        resizeTimer = null;
                        try {
                            if (typeof echarts === 'undefined' || !echarts.getInstanceByDom) return;
                            var doc = document.documentElement;
                            if (!doc || doc.clientWidth === 0 || doc.clientHeight === 0) return;
                            var divs = document.getElementsByTagName('div');
                            for (var i = 0; i < divs.length; i++) {
                                var el = divs[i];
                                if (!domOk(el)) continue;
                                var inst = echarts.getInstanceByDom(el);
                                if (inst && typeof inst.resize === 'function') {
                                    try { inst.resize(); } catch (err) {}
                                }
                            }
                        } catch (e) {}
                    }, RO_DEBOUNCE_MS);
                }

                var poll = 0;
                function patchEchartsInit() {
                    if (typeof echarts === 'undefined' || typeof echarts.init !== 'function') {
                        if (poll++ < 400) setTimeout(patchEchartsInit, 25);
                        return;
                    }
                    if (echarts.__gigaboardPatchedInit) return;
                    echarts.__gigaboardPatchedInit = true;
                    var origInit = echarts.init;
                    echarts.init = function(dom, theme, opts) {
                        try {
                            if (dom && dom.nodeType === 1) {
                                var w = dom.clientWidth;
                                var h = dom.clientHeight;
                                if (w === 0 || h === 0) {
                                    if (!dom.style.minHeight) dom.style.minHeight = '200px';
                                    if (!dom.style.minWidth) dom.style.minWidth = '100%';
                                    dom.style.boxSizing = 'border-box';
                                }
                            }
                        } catch (e) {}
                        var chart = origInit.call(echarts, dom, theme, opts);
                        return wrapChartResize(chart);
                    };
                }
                patchEchartsInit();
                window.addEventListener('load', function() {
                    requestAnimationFrame(function() {
                        requestAnimationFrame(gigaboardResizeAllCharts);
                    });
                });
                if (typeof ResizeObserver !== 'undefined') {
                    function roObserve() {
                        if (!document.body) return;
                        var ro = new ResizeObserver(function() {
                            requestAnimationFrame(function() {
                                gigaboardResizeAllCharts();
                            });
                        });
                        ro.observe(document.body);
                    }
                    if (document.body) roObserve();
                    else document.addEventListener('DOMContentLoaded', roObserve);
                }
            })();

            window.__GIGABOARD_API_READY = true;
        </script>`
}

/**
 * Fixes double-escaped newlines/tabs in widget HTML code.
 *
 * GigaChat sometimes returns \\n instead of \n in JSON strings.
 * After JSON.parse(), these become literal 2-char sequences (backslash + n)
 * instead of real newline characters.
 *
 * IMPORTANT: only unescape when the ENTIRE HTML is on a single line
 * (genuinely double-escaped). Multi-line HTML already has correct formatting;
 * its \n sequences inside <script> are valid JS escapes (e.g. formatter: '{b}\n{c}%')
 * and replacing them would cause SyntaxError.
 */
export function unescapeWidgetHtml(html: string): string {
    if (!html) return html

    const hasRealNewlines = html.includes('\n')
    const hasEscapedNewlines = html.includes('\\n')

    if (!hasRealNewlines && hasEscapedNewlines && html.includes('<')) {
        return html
            .replace(/\\n/g, '\n')
            .replace(/\\t/g, '\t')
            .replace(/\\"/g, '"')
    }
    return html
}

/**
 * Injects the API script into a full HTML document string.
 * Attempts to place it in <head>, then <body>, then prepends.
 */
export function injectApiScript(html: string, apiScript: string): string {
    if (html.includes('<head>')) {
        return html.replace('<head>', '<head>' + apiScript)
    } else if (html.includes('<body>')) {
        return html.replace('<body>', '<body>' + apiScript)
    }
    return apiScript + html
}
