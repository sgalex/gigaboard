#!/bin/bash
# GigaBoard Frontend Development Server

echo "🎨 Starting GigaBoard Frontend..."
cd "$(dirname "$0")"
npm --workspace apps/web run dev
