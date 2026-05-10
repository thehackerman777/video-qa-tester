#!/usr/bin/env bash
# ============================================================
# Video QA Tester — Deploy Script
# ============================================================
# Deploy to AWS VPS or K8s cluster.
#
# Usage:
#   ./scripts/deploy.sh docker    # Deploy via Docker Compose
#   ./scripts/deploy.sh k8s       # Deploy via kubectl

set -euo pipefail

MODE="${1:-docker}"

case "$MODE" in
    docker)
        echo "🚀 Deploying via Docker Compose..."

        # Build images
        echo "Building Docker images..."
        docker compose build

        # Start services
        echo "Starting services..."
        docker compose up -d

        # Check health
        echo "Checking orchestrator health..."
        for i in {1..10}; do
            if curl -sf http://localhost:3000/health > /dev/null 2>&1; then
                echo "✅ Orchestrator is healthy!"
                break
            fi
            echo "Waiting for orchestrator... ($i/10)"
            sleep 3
        done

        echo ""
        echo "✅ Deployment complete!"
        echo "   API:       http://localhost:3000"
        echo "   Grafana:   http://localhost:3001"
        echo "   Prometheus: http://localhost:9090"
        ;;

    k8s)
        echo "🚀 Deploying via kubectl..."

        if ! command -v kubectl &> /dev/null; then
            echo "❌ kubectl not found. Install it first."
            exit 1
        fi

        # Create namespace
        kubectl create namespace videoqa --dry-run=client -o yaml | kubectl apply -f -

        # Apply manifests
        kubectl apply -k k8s/manifests/

        # Wait for deployments
        echo "Waiting for deployments..."
        kubectl -n videoqa rollout status deployment/videoqa-orchestrator
        kubectl -n videoqa rollout status deployment/videoqa-worker

        # Get service info
        echo ""
        echo "✅ Deployment complete!"
        kubectl -n videoqa get svc,pods
        ;;

    *)
        echo "Usage: $0 {docker|k8s}"
        exit 1
        ;;
esac
