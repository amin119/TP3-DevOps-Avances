// pricing-engine (Service B) — moteur de calcul tarifaire GET /price.
//
// Aucune bibliothèque d'observabilité : la télémétrie est extraite par eBPF (Beyla).
//
// Variables d'environnement d'injection de fautes :
//   BASE_LATENCY_MS   latence "normale" de traitement (ms)          défaut 0
//   SLOW_PERCENT      % de requêtes lentes (0-100)                   défaut 0
//   SLOW_LATENCY_MS   latence des requêtes lentes (ms)               défaut 0
//   JITTER_MS         latence aléatoire uniforme ajoutée [0,JITTER]  défaut 0
//   ERROR_RATE        % de réponses HTTP 500 (0-100)                 défaut 0
//   CPU_ITERATIONS    nb d'itérations SHA-256 (charge CPU) / requête défaut 0
package main

import (
	"crypto/sha256"
	"encoding/json"
	"log"
	"math/rand/v2"
	"net/http"
	"os"
	"strconv"
	"time"
)

type config struct {
	baseLatency, slowLatency, jitter time.Duration
	slowPercent, errorRate           float64
	cpuIterations                    int
}

func envFloat(k string, d float64) float64 {
	if v, err := strconv.ParseFloat(os.Getenv(k), 64); err == nil {
		return v
	}
	return d
}

func loadConfig() config {
	ms := func(k string) time.Duration { return time.Duration(envFloat(k, 0) * float64(time.Millisecond)) }
	return config{
		baseLatency:   ms("BASE_LATENCY_MS"),
		slowLatency:   ms("SLOW_LATENCY_MS"),
		jitter:        ms("JITTER_MS"),
		slowPercent:   envFloat("SLOW_PERCENT", 0),
		errorRate:     envFloat("ERROR_RATE", 0),
		cpuIterations: int(envFloat("CPU_ITERATIONS", 0)),
	}
}

// burnCPU : travail CPU pur (hachages SHA-256 successifs).
func burnCPU(n int) byte {
	h := sha256.Sum256([]byte("pricing"))
	for i := 0; i < n; i++ {
		h = sha256.Sum256(h[:])
	}
	return h[0]
}

func main() {
	cfg := loadConfig()
	log.Printf("pricing-engine config: %+v", cfg)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("GET /price", func(w http.ResponseWriter, r *http.Request) {
		// 1) Charge CPU
		seed := burnCPU(cfg.cpuIterations)

		// 2) Latence : bimodale (rapide / lente) + gigue aléatoire
		d := cfg.baseLatency
		if rand.Float64()*100 < cfg.slowPercent {
			d = cfg.slowLatency
		}
		if cfg.jitter > 0 {
			d += time.Duration(rand.Int64N(int64(cfg.jitter)))
		}
		time.Sleep(d)

		// 3) Injection d'erreurs HTTP 500
		if rand.Float64()*100 < cfg.errorRate {
			http.Error(w, `{"error":"internal pricing error"}`, http.StatusInternalServerError)
			return
		}

		qty, _ := strconv.Atoi(r.URL.Query().Get("qty"))
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"sku":        r.URL.Query().Get("sku"),
			"quantity":   qty,
			"unit_price": 19.99 + float64(seed%10)/100,
			"currency":   "EUR",
		})
	})

	log.Fatal(http.ListenAndServe(":8080", mux))
}
