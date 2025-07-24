#!/bin/bash

# NBA Production Workflow Manager

case "$1" in
    start)
        echo "🚀 Starting NBA Production Workflow (6x daily)..."
        crontab nba_crontab.txt
        echo "✅ Cron jobs installed! Schedule:"
        echo "   8:00 AM, 12:00 PM, 4:00 PM, 8:00 PM, 11:00 PM, 2:00 AM"
        echo "📊 Monitor with: ./manage_nba_workflow.sh logs"
        ;;
    stop)
        echo "🛑 Stopping NBA Production Workflow..."
        crontab -r
        echo "✅ All cron jobs removed"
        ;;
    status)
        echo "📋 Current NBA workflow cron jobs:"
        crontab -l 2>/dev/null | grep "run_production_nba.sh" || echo "❌ No NBA workflow jobs found"
        ;;
    logs)
        echo "📊 NBA Production Workflow Logs:"
        echo "================================"
        if [ -f "nba_production.log" ]; then
            tail -20 nba_production.log
        else
            echo "❌ No log file found yet"
        fi
        ;;
    watch)
        echo "👀 Watching NBA workflow logs live (Ctrl+C to exit)..."
        tail -f nba_production.log
        ;;
    test)
        echo "🧪 Testing NBA workflow manually..."
        ./run_production_nba.sh
        ;;
    *)
        echo "NBA Production Workflow Manager"
        echo "=============================="
        echo "Usage: $0 {start|stop|status|logs|watch|test}"
        echo ""
        echo "Commands:"
        echo "  start  - Install 6x daily cron jobs"
        echo "  stop   - Remove all cron jobs"  
        echo "  status - Show current cron jobs"
        echo "  logs   - Show recent log entries"
        echo "  watch  - Watch logs live"
        echo "  test   - Run workflow manually"
        ;;
esac 