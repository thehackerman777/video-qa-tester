// ============================================================
// Proxy Rotator — Rust
// ============================================================
// Gestiona un pool de proxies SOCKS5 rotativos.
// Cada instancia de navegador obtiene una IP diferente.
//
// Estrategias de pool:
// - AWS EC2: lanza instancias como exit nodes
// - Archivo: lee proxies desde un archivo
// - Generados: usa IPs de proveedores

use clap::Parser;
use rand::seq::SliceRandom;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Parser)]
#[command(author, version, about = "SOCKS5 proxy pool rotator")]
struct Args {
    /// Puerto del servidor proxy pool
    #[arg(short, long, default_value_t = 1080)]
    port: u16,

    /// Tamaño del pool
    #[arg(short, long, default_value_t = 10)]
    pool_size: u8,

    /// Fuente de proxies: auto, file, aws
    #[arg(short, long, default_value = "auto")]
    source: String,

    /// Archivo con lista de proxies (formato: ip:puerto por línea)
    #[arg(short, long)]
    file: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ProxyEntry {
    address: String,
    protocol: String, // socks5, http, https
    region: String,
    alive: bool,
    latency_ms: u64,
    last_used: u64,
}

struct ProxyPool {
    proxies: Vec<ProxyEntry>,
    usage_count: HashMap<String, u64>,
}

impl ProxyPool {
    fn new() -> Self {
        Self {
            proxies: Vec::new(),
            usage_count: HashMap::new(),
        }
    }

    /// Carga proxies desde pool estático (para pruebas)
    fn load_static(&mut self, count: u8) {
        // En producción, estos vendrían de AWS/archivo
        for i in 0..count {
            self.proxies.push(ProxyEntry {
                address: format!("proxy-{}.local:9050", i),
                protocol: "socks5".into(),
                region: "us-east-1".into(),
                alive: true,
                latency_ms: 50 + (i as u64 * 10),
                last_used: 0,
            });
        }
    }

    fn get_random(&mut self) -> Option<&ProxyEntry> {
        let alive: Vec<usize> = self
            .proxies
            .iter()
            .enumerate()
            .filter(|(_, p)| p.alive)
            .map(|(i, _)| i)
            .collect();

        let idx = alive.choose(&mut rand::thread_rng())?;
        let proxy = &self.proxies[*idx];
        self.usage_count
            .entry(proxy.address.clone())
            .and_modify(|c| *c += 1)
            .or_insert(1);
        Some(proxy)
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();
    println!("🔁 Proxy Rotator v0.1");
    println!("   Pool size: {}", args.pool_size);
    println!("   Source: {}", args.source);
    println!("   Port: {}", args.port);

    let pool = Arc::new(RwLock::new(ProxyPool::new()));

    // Cargar pool inicial
    {
        let mut p = pool.write().await;
        p.load_static(args.pool_size);
        println!("   Loaded {} proxies", p.proxies.len());
    }

    // HTTP endpoint para que los workers obtengan proxies
    let pool_clone = pool.clone();
    let router = axum::Router::new()
        .route("/proxy", axum::routing::get(move || {
            let p = pool_clone.clone();
            async move {
                let mut pool = p.write().await;
                match pool.get_random() {
                    Some(proxy) => {
                        let json = serde_json::to_string(&proxy).unwrap_or_default();
                        axum::response::Json(serde_json::json!({
                            "status": "ok",
                            "proxy": proxy.address,
                            "protocol": proxy.protocol,
                            "region": proxy.region,
                        }))
                    }
                    None => axum::response::Json(serde_json::json!({
                        "status": "error",
                        "message": "No proxies available"
                    })),
                }
            }
        }))
        .route("/health", axum::routing::get(|| async {
            axum::response::Json(serde_json::json!({"status": "ok"}))
        }));

    let addr = format!("0.0.0.0:{}", args.port);
    println!("   Listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, router).await?;

    Ok(())
}
