/**
 * Имя ZIP при экспорте проекта: ProjectName_YYYYMMDD_hhmm.zip
 * (локальные дата и время момента экспорта).
 */
export function buildProjectExportZipFilename(projectName: string): string {
    const now = new Date()
    const y = now.getFullYear()
    const mo = String(now.getMonth() + 1).padStart(2, '0')
    const d = String(now.getDate()).padStart(2, '0')
    const ymd = `${y}${mo}${d}`
    const hh = String(now.getHours()).padStart(2, '0')
    const mm = String(now.getMinutes()).padStart(2, '0')

    let base = projectName.trim() || 'project'
    base = base.replace(/[\\/:*?"<>|]/g, '_')
    base = base.replace(/\s+/g, '_')
    base = base.replace(/_+/g, '_').replace(/^_|_$/g, '')
    if (!base) base = 'project'
    if (base.length > 120) {
        base = base.slice(0, 120)
    }

    return `${base}_${ymd}_${hh}${mm}.zip`
}
