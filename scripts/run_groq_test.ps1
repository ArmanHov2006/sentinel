# Sentinel Groq Test: 20 questions (10 with PII) x 5 rounds
# Requires: GROQ_API_KEY in .env, Sentinel running, Redis running

$baseUrl = "http://localhost:8000"
$model = "llama-3.1-8b-instant"

# 20 questions — alternating normal and PII
# Normal questions (10): unique, varied topics
# PII questions (10): contain phone, email, SSN, credit card, IP, address, etc.
$questions = @(
    "Explain quantum entanglement in one sentence.",                         # 1  normal
    "My phone number is 555-867-5309, add me to the list.",                 # 2  PII phone
    "What is the difference between TCP and UDP?",                          # 3  normal
    "Send the contract to sarah.jones@bigcorp.com please.",                 # 4  PII email
    "Why do leaves change color in autumn?",                                # 5  normal
    "My social security number is 078-05-1120 for verification.",           # 6  PII SSN
    "What are the main causes of the French Revolution?",                   # 7  normal
    "Please charge credit card 4532-1234-5678-9012 for the order.",        # 8  PII credit card
    "How does a blockchain consensus mechanism work?",                      # 9  normal
    "Ship the package to 742 Evergreen Terrace, Springfield IL 62704.",    # 10 PII address
    "What is the Turing test and has any AI passed it?",                    # 11 normal
    "Reach me at mike.chen@startup.io for the interview.",                  # 12 PII email
    "Explain the difference between machine learning and deep learning.",   # 13 normal
    "My direct line is +1-212-555-0147, call anytime.",                    # 14 PII phone
    "What causes black holes to form?",                                     # 15 normal
    "The database server is at 10.0.0.42 port 5432.",                      # 16 PII IP
    "How do vaccines train the immune system?",                             # 17 normal
    "Forward the receipt to accounting@example.org.",                       # 18 PII email
    "What is the significance of the Rosetta Stone?",                       # 19 normal
    "My UK NHS number is 943-476-5919 for the medical record."             # 20 PII NHS
)

$totalRounds = 5

# ── Step 1: Reset everything (metrics + Redis cache) ──
Write-Host "`n=== RESETTING ALL STATS AND CACHE ===" -ForegroundColor Cyan
try {
    $r = Invoke-RestMethod -Uri "$baseUrl/metrics/reset" -Method POST
    Write-Host "  $($r.message)" -ForegroundColor Green
} catch {
    Write-Host "  Reset failed: $_" -ForegroundColor Red
    exit 1
}
Start-Sleep -Seconds 1

# ── Step 2: Run 5 rounds ──
Write-Host "`n=== SENDING 5 ROUNDS x 20 QUESTIONS (10 PII each) ===" -ForegroundColor Cyan
Write-Host "  Round 1 = all fresh (cache misses, API calls)"
Write-Host "  Rounds 2-5 = repeats (should be cache hits)`n"

$round = 1
while ($round -le $totalRounds) {
    Write-Host "--- Round $round of $totalRounds ---" -ForegroundColor Yellow
    $qNum = 0
    foreach ($q in $questions) {
        $qNum++
        $isPII = ($qNum % 2 -eq 0)
        $tag = if ($isPII) { "[PII]" } else { "     " }
        $body = @{model=$model; messages=@(@{role="user"; content=$q})} | ConvertTo-Json -Depth 3
        try {
            $resp = Invoke-RestMethod -Uri "$baseUrl/v1/chat/completions" -Method POST -ContentType "application/json" -Body $body
            $ans = $resp.choices[0].message.content
            if ($ans.Length -gt 55) { $ans = $ans.Substring(0, 52) + "..." }
            Write-Host "  $tag $qNum. OK - $ans"
        } catch {
            $code = $_.Exception.Response.StatusCode.value__
            Write-Host "  $tag $qNum. HTTP $code" -ForegroundColor Red
        }
        Start-Sleep -Milliseconds 800
    }
    Write-Host ""
    $round++
}

# ── Step 3: Print final metrics ──
Write-Host "=== FINAL RESULTS ===" -ForegroundColor Cyan
$m = Invoke-RestMethod -Uri "$baseUrl/metrics"

$total    = $m.requests.total
$hits     = $m.cache.hits
$misses   = $m.cache.misses
$hitRate  = [math]::Round($m.cache.hit_rate * 100, 1)
$piiDet   = $m.security.pii_detections
$piiBlock = $m.security.pii_blocks
$rateL    = $m.security.rate_limit_rejections
$cbTrips  = $m.security.circuit_breaker_trips
$avg      = [math]::Round($m.performance.avg_response_time_ms, 1)
$p95      = [math]::Round($m.performance.p95_response_time_ms, 1)

Write-Host ""
Write-Host "  Total requests:     $total"
Write-Host "  Avg response time:  ${avg}ms (p95: ${p95}ms)"
Write-Host ""
Write-Host "  Cache hits:         $hits"
Write-Host "  Cache misses:       $misses"
Write-Host "  Cache hit rate:     ${hitRate}%"
Write-Host ""
Write-Host "  PII detections:     $piiDet"
Write-Host "  PII blocked:        $piiBlock"
Write-Host "  Rate limited:       $rateL"
Write-Host "  CB trips:           $cbTrips"
Write-Host ""

# Expected:
#   Round 1: 20 misses (fresh questions, all go to Groq API)
#   Rounds 2-5: 80 hits (same questions, served from Redis cache)
#   Cache hit rate: ~80% (80 hits / 100 total)
#   PII detections: 10 per round x 5 = ~50 (one per PII question)
#   But rounds 2-5 PII questions hit cache BEFORE PII scan? No — PII scan runs first.
#   So PII detections: ~50 total

Write-Host "  Expected: ~80% cache hit rate, ~50 PII detections" -ForegroundColor DarkGray
Write-Host "`n  Dashboard: $baseUrl/dashboard" -ForegroundColor Green
