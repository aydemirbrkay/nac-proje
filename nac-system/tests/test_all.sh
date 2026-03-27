#!/bin/bash
# ============================================================
# NAC Sistemi — Otomatik Test Scripti
# ============================================================
# Bu script tüm bileşenleri sırasıyla test eder:
#   1. Servis healthcheck'leri
#   2. PAP Authentication
#   3. MAB Authentication
#   4. Authorization (VLAN kontrol)
#   5. Accounting (Start → Interim → Stop)
#   6. Rate Limiting
#   7. FastAPI endpoint'leri
#
# Kullanım: chmod +x tests/test_all.sh && ./tests/test_all.sh
# ============================================================

set -e  # Hata olursa dur

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

print_header() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
}

check_result() {
    if [ $1 -eq 0 ]; then
        echo -e "  ${GREEN}✓ PASS:${NC} $2"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗ FAIL:${NC} $2"
        FAIL=$((FAIL + 1))
    fi
}

API_URL="http://localhost:8000"

# ── 0. Servislerin Hazır Olmasını Bekle ──
print_header "0. Servis Kontrolleri"
echo "Servislerin hazır olması bekleniyor..."
sleep 3

curl -sf "$API_URL/health" > /dev/null 2>&1
check_result $? "FastAPI healthcheck"

# ── 1. PAP Authentication Testleri ──
print_header "1. PAP Authentication"

# Başarılı giriş
echo "  → admin_ali ile giriş deneniyor..."
RESPONSE=$(curl -sf -X POST "$API_URL/auth" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin_ali","password":"Admin1234!"}')
echo "$RESPONSE" | grep -q '"accept"'
check_result $? "Admin kullanıcı başarılı giriş"

# Başarılı giriş - employee
RESPONSE=$(curl -sf -X POST "$API_URL/auth" \
    -H "Content-Type: application/json" \
    -d '{"username":"emp_mehmet","password":"Emp1234!"}')
echo "$RESPONSE" | grep -q '"accept"'
check_result $? "Employee kullanıcı başarılı giriş"

# Yanlış şifre
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/auth" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin_ali","password":"YanlisParola"}')
[ "$HTTP_CODE" = "401" ]
check_result $? "Yanlış şifre → reject (HTTP 401)"

# Mevcut olmayan kullanıcı
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/auth" \
    -H "Content-Type: application/json" \
    -d '{"username":"yok_kullanici","password":"test123"}')
[ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "404" ]
check_result $? "Mevcut olmayan kullanıcı → reject"

# ── 2. MAB Authentication Testleri ──
print_header "2. MAB Authentication"

# Kayıtlı cihaz
RESPONSE=$(curl -sf -X POST "$API_URL/auth" \
    -H "Content-Type: application/json" \
    -d '{"username":"AA:BB:CC:DD:EE:01","calling_station_id":"AA:BB:CC:DD:EE:01"}')
echo "$RESPONSE" | grep -q '"accept"'
check_result $? "Kayıtlı MAC adresi → accept"

# Bilinmeyen cihaz → guest VLAN
RESPONSE=$(curl -sf -X POST "$API_URL/auth" \
    -H "Content-Type: application/json" \
    -d '{"username":"FF:FF:FF:FF:FF:FF","calling_station_id":"FF:FF:FF:FF:FF:FF"}')
echo "$RESPONSE" | grep -q '"accept"'
check_result $? "Bilinmeyen MAC → guest VLAN accept"
echo "$RESPONSE" | grep -q '"30"'
check_result $? "Bilinmeyen MAC → VLAN 30 (guest) atandı"

# ── 3. Authorization Testleri ──
print_header "3. Authorization (VLAN Atama)"

# Admin → VLAN 10
RESPONSE=$(curl -sf -X POST "$API_URL/authorize" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin_ali"}')
echo "$RESPONSE" | grep -q '"10"'
check_result $? "Admin grubu → VLAN 10"

# Employee → VLAN 20
RESPONSE=$(curl -sf -X POST "$API_URL/authorize" \
    -H "Content-Type: application/json" \
    -d '{"username":"emp_mehmet"}')
echo "$RESPONSE" | grep -q '"20"'
check_result $? "Employee grubu → VLAN 20"

# Guest → VLAN 30
RESPONSE=$(curl -sf -X POST "$API_URL/authorize" \
    -H "Content-Type: application/json" \
    -d '{"username":"guest_user"}')
echo "$RESPONSE" | grep -q '"30"'
check_result $? "Guest grubu → VLAN 30"

# MAB cihaz authorize
RESPONSE=$(curl -sf -X POST "$API_URL/authorize" \
    -H "Content-Type: application/json" \
    -d '{"username":"AA:BB:CC:DD:EE:01","calling_station_id":"AA:BB:CC:DD:EE:01"}')
echo "$RESPONSE" | grep -q '"40"'
check_result $? "IoT cihaz → VLAN 40"

# ── 4. Accounting Testleri ──
print_header "4. Accounting (Oturum Kayıt)"

SESSION_ID="test-session-$(date +%s)"
UNIQUE_ID="unique-$(date +%s)"

# Accounting Start
RESPONSE=$(curl -sf -X POST "$API_URL/accounting" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"admin_ali\",\"acct_status_type\":\"Start\",\"acct_session_id\":\"$SESSION_ID\",\"acct_unique_session_id\":\"$UNIQUE_ID\",\"nas_ip_address\":\"192.168.1.1\"}")
echo "$RESPONSE" | grep -q '"ok"'
check_result $? "Accounting Start kaydedildi"

# Aktif oturum Redis'te olmalı
sleep 1
RESPONSE=$(curl -sf "$API_URL/sessions/active")
echo "$RESPONSE" | grep -q "$SESSION_ID"
check_result $? "Aktif oturum Redis'te mevcut"

# Accounting Interim-Update
RESPONSE=$(curl -sf -X POST "$API_URL/accounting" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"admin_ali\",\"acct_status_type\":\"Interim-Update\",\"acct_session_id\":\"$SESSION_ID\",\"acct_unique_session_id\":\"$UNIQUE_ID\",\"nas_ip_address\":\"192.168.1.1\",\"acct_session_time\":120,\"acct_input_octets\":50000,\"acct_output_octets\":200000}")
echo "$RESPONSE" | grep -q '"ok"'
check_result $? "Accounting Interim-Update kaydedildi"

# Accounting Stop
RESPONSE=$(curl -sf -X POST "$API_URL/accounting" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"admin_ali\",\"acct_status_type\":\"Stop\",\"acct_session_id\":\"$SESSION_ID\",\"acct_unique_session_id\":\"$UNIQUE_ID\",\"nas_ip_address\":\"192.168.1.1\",\"acct_session_time\":300,\"acct_input_octets\":100000,\"acct_output_octets\":500000,\"acct_terminate_cause\":\"User-Request\"}")
echo "$RESPONSE" | grep -q '"ok"'
check_result $? "Accounting Stop kaydedildi"

# Stop sonrası Redis'ten silinmiş olmalı
sleep 1
RESPONSE=$(curl -sf "$API_URL/sessions/active")
echo "$RESPONSE" | grep -qv "$SESSION_ID" || echo "$RESPONSE" | grep -q '\[\]'
check_result $? "Oturum kapandıktan sonra Redis'ten silindi"

# ── 5. Kullanıcı Listesi ──
print_header "5. Kullanıcı Listesi"

TOKEN=$(curl -sf -X POST "$API_URL/admin/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin_ali","password":"Admin1234!"}' 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
RESPONSE=$(curl -sf "$API_URL/users" -H "Authorization: Bearer $TOKEN" 2>/dev/null)
echo "$RESPONSE" | grep -q "admin_ali"
check_result $? "/users endpoint'i JWT ile çalışıyor"

# ── 6. Rate Limiting ──
print_header "6. Rate Limiting"

echo "  → 6 başarısız giriş denemesi yapılıyor..."
for i in $(seq 1 6); do
    curl -s -o /dev/null -X POST "$API_URL/auth" \
        -H "Content-Type: application/json" \
        -d '{"username":"rate_test_user","password":"wrong"}' 2>&1
done

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/auth" \
    -H "Content-Type: application/json" \
    -d '{"username":"rate_test_user","password":"wrong"}')
[ "$HTTP_CODE" = "429" ]
check_result $? "Rate limiting aktif — hesap kilitlendi"

# ── SONUÇLAR ──
print_header "TEST SONUÇLARI"
echo -e "  ${GREEN}Başarılı: $PASS${NC}"
echo -e "  ${RED}Başarısız: $FAIL${NC}"
TOTAL=$((PASS + FAIL))
echo -e "  Toplam: $TOTAL test"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}Tüm testler başarılı!${NC}"
    exit 0
else
    echo -e "${RED}$FAIL test başarısız!${NC}"
    exit 1
fi
