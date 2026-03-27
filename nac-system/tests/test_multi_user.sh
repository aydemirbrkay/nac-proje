#!/bin/bash
# ============================================================
# NAC Sistemi — Çoklu Kullanıcı Senaryo Testi
# ============================================================
# Bu script farklı VLAN'lardaki kullanıcıların bağlantılarını
# simüle eder. Docker oturumlarını gözlemlemek için kullanılır.
#
# Kullanım:
#   chmod +x tests/test_multi_user.sh
#   ./tests/test_multi_user.sh
#
# Docker'dan oturumları takip etmek için başka bir terminalde:
#   curl http://localhost:8000/sessions/active | python3 -m json.tool
#   curl http://localhost:8000/users | python3 -m json.tool
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

API_URL="http://localhost:8000"

print_header() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_vlan() {
    echo -e "${MAGENTA}  ┌─ VLAN $1 ($2)${NC}"
}

print_result() {
    local status=$1
    local user=$2
    local detail=$3
    if [ "$status" = "accept" ]; then
        echo -e "  ${GREEN}│ ✓ $user → $detail${NC}"
    else
        echo -e "  ${RED}│ ✗ $user → $detail${NC}"
    fi
}

print_vlan_end() {
    echo -e "${MAGENTA}  └────────────────────────────────────────${NC}"
}

# Fonksiyon: Kimlik doğrulama
auth_user() {
    local user=$1
    local pass=$2
    curl -sf -X POST "$API_URL/auth" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$user\",\"password\":\"$pass\"}" 2>/dev/null
}

# Fonksiyon: MAB kimlik doğrulama
auth_mac() {
    local mac=$1
    curl -sf -X POST "$API_URL/auth" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$mac\",\"calling_station_id\":\"$mac\"}" 2>/dev/null
}

# Fonksiyon: Yetkilendirme (VLAN atama)
authorize_user() {
    local user=$1
    curl -sf -X POST "$API_URL/authorize" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$user\"}" 2>/dev/null
}

# Fonksiyon: Oturum başlat
start_session() {
    local user=$1
    local session_id=$2
    local unique_id=$3
    local nas_ip=$4
    local nas_port=$5
    local mac=$6
    curl -sf -X POST "$API_URL/accounting" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$user\",\"acct_status_type\":\"Start\",\"acct_session_id\":\"$session_id\",\"acct_unique_session_id\":\"$unique_id\",\"nas_ip_address\":\"$nas_ip\",\"nas_port_id\":\"$nas_port\",\"calling_station_id\":\"$mac\"}" 2>/dev/null
}

# Fonksiyon: Oturum güncelle
update_session() {
    local user=$1
    local session_id=$2
    local unique_id=$3
    local nas_ip=$4
    local session_time=$5
    local input=$6
    local output=$7
    curl -sf -X POST "$API_URL/accounting" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$user\",\"acct_status_type\":\"Interim-Update\",\"acct_session_id\":\"$session_id\",\"acct_unique_session_id\":\"$unique_id\",\"nas_ip_address\":\"$nas_ip\",\"acct_session_time\":$session_time,\"acct_input_octets\":$input,\"acct_output_octets\":$output}" 2>/dev/null
}

# Fonksiyon: Oturum kapat
stop_session() {
    local user=$1
    local session_id=$2
    local unique_id=$3
    local nas_ip=$4
    local session_time=$5
    local input=$6
    local output=$7
    local cause=$8
    curl -sf -X POST "$API_URL/accounting" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$user\",\"acct_status_type\":\"Stop\",\"acct_session_id\":\"$session_id\",\"acct_unique_session_id\":\"$unique_id\",\"nas_ip_address\":\"$nas_ip\",\"acct_session_time\":$session_time,\"acct_input_octets\":$input,\"acct_output_octets\":$output,\"acct_terminate_cause\":\"$cause\"}" 2>/dev/null
}

# ══════════════════════════════════════════════
# SENARYO 1: Tüm Kullanıcıların Kimlik Doğrulaması
# ══════════════════════════════════════════════
print_header "SENARYO 1: Tüm Kullanıcıların Kimlik Doğrulaması"

# --- VLAN 10: Admin ---
print_vlan "10" "Admin"
for user_pass in "admin_ali:Admin1234!" "admin_zeynep:Zeynep2024!" "admin_burak:Burak2024!"; do
    IFS=':' read -r user pass <<< "$user_pass"
    RESP=$(auth_user "$user" "$pass")
    if echo "$RESP" | grep -q '"accept"'; then
        print_result "accept" "$user" "Kimlik doğrulandı"
    else
        print_result "reject" "$user" "REDDEDILDI: $RESP"
    fi
done
print_vlan_end

# --- VLAN 20: Employee ---
print_vlan "20" "Employee"
for user_pass in "emp_mehmet:Emp1234!" "emp_ayse:Emp5678!" "emp_fatma:Fatma2024!" "emp_can:Can2024!" "emp_deniz:Deniz2024!"; do
    IFS=':' read -r user pass <<< "$user_pass"
    RESP=$(auth_user "$user" "$pass")
    if echo "$RESP" | grep -q '"accept"'; then
        print_result "accept" "$user" "Kimlik doğrulandı"
    else
        print_result "reject" "$user" "REDDEDILDI: $RESP"
    fi
done
print_vlan_end

# --- VLAN 30: Guest ---
print_vlan "30" "Guest"
for user_pass in "guest_user:Guest1234!" "guest_ahmet:Ahmet2024!" "guest_elif:Elif2024!" "guest_tamir:Tamir2024!"; do
    IFS=':' read -r user pass <<< "$user_pass"
    RESP=$(auth_user "$user" "$pass")
    if echo "$RESP" | grep -q '"accept"'; then
        print_result "accept" "$user" "Kimlik doğrulandı"
    else
        print_result "reject" "$user" "REDDEDILDI: $RESP"
    fi
done
print_vlan_end

# --- VLAN 40: IoT (MAB) ---
print_vlan "40" "IoT Devices"
for mac_name in "AA:BB:CC:DD:EE:01:Kat-1 Yazici" "AA:BB:CC:DD:EE:03:Guvenlik Kamerasi" "AA:BB:CC:DD:EE:05:Kat-2 Yazici" "AA:BB:CC:DD:EE:06:Sicaklik Sensoru" "AA:BB:CC:DD:EE:07:Kapi Kilidi"; do
    IFS=':' read -r a b c d e f name <<< "$mac_name"
    mac="$a:$b:$c:$d:$e:$f"
    RESP=$(auth_mac "$mac")
    if echo "$RESP" | grep -q '"accept"'; then
        print_result "accept" "$mac" "$name — MAC doğrulandı"
    else
        print_result "reject" "$mac" "$name — REDDEDILDI"
    fi
done
print_vlan_end

# --- Bilinmeyen cihaz ---
echo ""
echo -e "${YELLOW}  → Bilinmeyen cihaz testi (guest VLAN'a düşmeli):${NC}"
RESP=$(auth_mac "11:22:33:44:55:66")
if echo "$RESP" | grep -q '"accept"'; then
    echo -e "  ${GREEN}  ✓ 11:22:33:44:55:66 → Guest VLAN'a yönlendirildi${NC}"
else
    echo -e "  ${RED}  ✗ 11:22:33:44:55:66 → Beklenmeyen sonuç: $RESP${NC}"
fi

# ══════════════════════════════════════════════
# SENARYO 2: VLAN Atama Kontrolü
# ══════════════════════════════════════════════
print_header "SENARYO 2: VLAN Atama Kontrolü (Her kullanıcı doğru VLAN'a düşmeli)"

echo -e "${YELLOW}  Kullanıcı              Beklenen VLAN  →  Atanan VLAN     Sonuç${NC}"
echo -e "${YELLOW}  ─────────────────────  ─────────────  →  ──────────────  ──────${NC}"

check_vlan() {
    local user=$1
    local expected_vlan=$2
    local group=$3
    RESP=$(authorize_user "$user")
    VLAN=$(echo "$RESP" | grep -o '"Tunnel-Private-Group-Id":"[^"]*"' | grep -o '[0-9]*')
    if [ "$VLAN" = "$expected_vlan" ]; then
        printf "  ${GREEN}%-23s %-14s →  VLAN %-10s ✓ DOĞRU${NC}\n" "$user" "VLAN $expected_vlan" "$VLAN"
    else
        printf "  ${RED}%-23s %-14s →  VLAN %-10s ✗ YANLIŞ${NC}\n" "$user" "VLAN $expected_vlan" "$VLAN"
    fi
}

# Admin kullanıcıları → VLAN 10
check_vlan "admin_ali" "10" "admin"
check_vlan "admin_zeynep" "10" "admin"
check_vlan "admin_burak" "10" "admin"

# Employee kullanıcıları → VLAN 20
check_vlan "emp_mehmet" "20" "employee"
check_vlan "emp_ayse" "20" "employee"
check_vlan "emp_fatma" "20" "employee"
check_vlan "emp_can" "20" "employee"
check_vlan "emp_deniz" "20" "employee"

# Guest kullanıcıları → VLAN 30
check_vlan "guest_user" "30" "guest"
check_vlan "guest_ahmet" "30" "guest"
check_vlan "guest_elif" "30" "guest"
check_vlan "guest_tamir" "30" "guest"

# ══════════════════════════════════════════════
# SENARYO 3: Eş Zamanlı Oturumlar (Farklı VLAN'lardan)
# ══════════════════════════════════════════════
print_header "SENARYO 3: Eş Zamanlı Oturumlar — Farklı VLAN'lardan Bağlantı"

TS=$(date +%s)

echo -e "${YELLOW}  Birden fazla kullanıcı aynı anda bağlanıyor...${NC}"
echo ""

# Her VLAN'dan birer kullanıcı bağlansın
start_session "admin_ali"    "sess-admin-$TS"    "uniq-admin-$TS"    "192.168.1.1" "Gi0/1"  "00:11:22:33:44:01"
echo -e "  ${GREEN}→ admin_ali     bağlandı (VLAN 10, Switch: 192.168.1.1, Port: Gi0/1)${NC}"

start_session "admin_zeynep" "sess-zeynep-$TS"   "uniq-zeynep-$TS"   "192.168.1.1" "Gi0/2"  "00:11:22:33:44:02"
echo -e "  ${GREEN}→ admin_zeynep  bağlandı (VLAN 10, Switch: 192.168.1.1, Port: Gi0/2)${NC}"

start_session "emp_mehmet"   "sess-mehmet-$TS"   "uniq-mehmet-$TS"   "192.168.1.2" "Gi0/1"  "00:11:22:33:44:03"
echo -e "  ${GREEN}→ emp_mehmet    bağlandı (VLAN 20, Switch: 192.168.1.2, Port: Gi0/1)${NC}"

start_session "emp_fatma"    "sess-fatma-$TS"    "uniq-fatma-$TS"    "192.168.1.2" "Gi0/5"  "00:11:22:33:44:04"
echo -e "  ${GREEN}→ emp_fatma     bağlandı (VLAN 20, Switch: 192.168.1.2, Port: Gi0/5)${NC}"

start_session "emp_can"      "sess-can-$TS"      "uniq-can-$TS"      "192.168.1.3" "Gi0/3"  "00:11:22:33:44:05"
echo -e "  ${GREEN}→ emp_can       bağlandı (VLAN 20, Switch: 192.168.1.3, Port: Gi0/3)${NC}"

start_session "guest_ahmet"  "sess-ahmet-$TS"    "uniq-ahmet-$TS"    "192.168.1.4" "Gi0/10" "00:11:22:33:44:06"
echo -e "  ${GREEN}→ guest_ahmet   bağlandı (VLAN 30, Switch: 192.168.1.4, Port: Gi0/10)${NC}"

start_session "guest_elif"   "sess-elif-$TS"     "uniq-elif-$TS"     "192.168.1.4" "Gi0/11" "00:11:22:33:44:07"
echo -e "  ${GREEN}→ guest_elif    bağlandı (VLAN 30, Switch: 192.168.1.4, Port: Gi0/11)${NC}"

echo ""
echo -e "${YELLOW}  ⏳ 3 saniye bekleniyor (oturumlar aktif)...${NC}"
echo -e "${YELLOW}  → Şimdi başka terminalde aktif oturumları kontrol edebilirsin:${NC}"
echo -e "${CYAN}    curl http://localhost:8000/sessions/active | python3 -m json.tool${NC}"
echo -e "${CYAN}    curl http://localhost:8000/users | python3 -m json.tool${NC}"
sleep 3

# Aktif oturum sayısını kontrol et
ACTIVE=$(curl -sf "$API_URL/sessions/active")
echo ""
echo -e "${MAGENTA}  📊 Aktif Oturumlar:${NC}"
echo "$ACTIVE" | python3 -m json.tool 2>/dev/null || echo "$ACTIVE"
echo ""

# ══════════════════════════════════════════════
# SENARYO 4: Oturum Güncelleme (Interim-Update)
# ══════════════════════════════════════════════
print_header "SENARYO 4: Trafik Simülasyonu (Interim-Update)"

echo -e "${YELLOW}  Kullanıcılar trafik üretiyor...${NC}"
echo ""

# Her kullanıcı farklı miktarda trafik üretsin
update_session "admin_ali"    "sess-admin-$TS"   "uniq-admin-$TS"   "192.168.1.1" 120  500000   2000000
echo -e "  admin_ali     → 120s, ↓500KB  ↑2MB   (yoğun admin trafiği)"

update_session "admin_zeynep" "sess-zeynep-$TS"  "uniq-zeynep-$TS"  "192.168.1.1" 110  300000   1500000
echo -e "  admin_zeynep  → 110s, ↓300KB  ↑1.5MB (normal admin trafiği)"

update_session "emp_mehmet"   "sess-mehmet-$TS"  "uniq-mehmet-$TS"  "192.168.1.2" 100  200000   800000
echo -e "  emp_mehmet    → 100s, ↓200KB  ↑800KB (normal çalışan trafiği)"

update_session "emp_fatma"    "sess-fatma-$TS"   "uniq-fatma-$TS"   "192.168.1.2" 95   150000   600000
echo -e "  emp_fatma     → 95s,  ↓150KB  ↑600KB (normal çalışan trafiği)"

update_session "emp_can"      "sess-can-$TS"     "uniq-can-$TS"     "192.168.1.3" 90   100000   400000
echo -e "  emp_can       → 90s,  ↓100KB  ↑400KB (hafif çalışan trafiği)"

update_session "guest_ahmet"  "sess-ahmet-$TS"   "uniq-ahmet-$TS"   "192.168.1.4" 80   50000    100000
echo -e "  guest_ahmet   → 80s,  ↓50KB   ↑100KB (kısıtlı misafir trafiği)"

update_session "guest_elif"   "sess-elif-$TS"    "uniq-elif-$TS"    "192.168.1.4" 75   30000    80000
echo -e "  guest_elif    → 75s,  ↓30KB   ↑80KB  (kısıtlı misafir trafiği)"

echo ""
echo -e "${YELLOW}  ⏳ 2 saniye bekleniyor...${NC}"
sleep 2

# ══════════════════════════════════════════════
# SENARYO 5: Bazı Kullanıcılar Çıkış Yapıyor
# ══════════════════════════════════════════════
print_header "SENARYO 5: Oturum Kapanışları"

echo -e "${YELLOW}  Bazı kullanıcılar bağlantıyı kesiyor...${NC}"
echo ""

stop_session "guest_ahmet" "sess-ahmet-$TS" "uniq-ahmet-$TS" "192.168.1.4" 180 80000 150000 "User-Request"
echo -e "  ${RED}✕ guest_ahmet   ayrıldı (sebep: User-Request — kendisi çıkış yaptı)${NC}"

stop_session "emp_can"     "sess-can-$TS"   "uniq-can-$TS"   "192.168.1.3" 200 120000 500000 "Idle-Timeout"
echo -e "  ${RED}✕ emp_can       ayrıldı (sebep: Idle-Timeout — boşta kaldı)${NC}"

stop_session "admin_ali"   "sess-admin-$TS" "uniq-admin-$TS" "192.168.1.1" 300 600000 2500000 "Admin-Reset"
echo -e "  ${RED}✕ admin_ali     ayrıldı (sebep: Admin-Reset — admin tarafından kesildi)${NC}"

echo ""
echo -e "${YELLOW}  ⏳ 2 saniye bekleniyor...${NC}"
sleep 2

# Kalan aktif oturumlar
ACTIVE=$(curl -sf "$API_URL/sessions/active")
echo ""
echo -e "${MAGENTA}  📊 Kalan Aktif Oturumlar (3 kullanıcı çıktıktan sonra):${NC}"
echo "$ACTIVE" | python3 -m json.tool 2>/dev/null || echo "$ACTIVE"

# ══════════════════════════════════════════════
# SENARYO 6: Yanlış Şifre Denemeleri
# ══════════════════════════════════════════════
print_header "SENARYO 6: Güvenlik — Başarısız Giriş Denemeleri"

echo -e "${YELLOW}  Farklı kullanıcılarla yanlış şifre denemeleri...${NC}"
echo ""

# Farklı kullanıcılarla yanlış şifre
for user in "admin_burak" "emp_deniz" "guest_tamir"; do
    RESP=$(auth_user "$user" "yanlis_sifre_123")
    echo -e "  ${RED}✗ $user → yanlış şifre → $(echo $RESP | grep -o '"[a-z]*"' | head -1)${NC}"
done

echo ""
echo -e "${YELLOW}  Aynı kullanıcıyla tekrarlı yanlış denemeler (rate limit testi)...${NC}"
echo ""

for i in $(seq 1 6); do
    RESP=$(auth_user "emp_deniz" "yanlis_sifre_$i")
    STATUS=$(echo "$RESP" | grep -o '"reject"\|"kilitli"\|"locked"' | head -1)
    echo -e "  Deneme $i → $STATUS"
done

# ══════════════════════════════════════════════
# SENARYO 7: Kalan Oturumları Kapat
# ══════════════════════════════════════════════
print_header "SENARYO 7: Tüm Oturumları Kapat"

stop_session "admin_zeynep" "sess-zeynep-$TS" "uniq-zeynep-$TS" "192.168.1.1" 400  400000  2000000 "User-Request"
echo -e "  ✕ admin_zeynep  ayrıldı"

stop_session "emp_mehmet"   "sess-mehmet-$TS" "uniq-mehmet-$TS" "192.168.1.2" 350  250000  1000000 "User-Request"
echo -e "  ✕ emp_mehmet     ayrıldı"

stop_session "emp_fatma"    "sess-fatma-$TS"  "uniq-fatma-$TS"  "192.168.1.2" 320  200000  800000  "Session-Timeout"
echo -e "  ✕ emp_fatma      ayrıldı (Session-Timeout)"

stop_session "guest_elif"   "sess-elif-$TS"   "uniq-elif-$TS"   "192.168.1.4" 280  50000   120000  "User-Request"
echo -e "  ✕ guest_elif     ayrıldı"

sleep 1

# Son kontrol
ACTIVE=$(curl -sf "$API_URL/sessions/active")
echo ""
echo -e "${MAGENTA}  📊 Final — Aktif Oturumlar:${NC}"
echo "$ACTIVE" | python3 -m json.tool 2>/dev/null || echo "$ACTIVE"

# ══════════════════════════════════════════════
# ÖZET
# ══════════════════════════════════════════════
print_header "KULLANICI VE VLAN ÖZETİ"

echo -e "${CYAN}  ┌──────────────────────────────────────────────────────────────┐${NC}"
echo -e "${CYAN}  │  VLAN 10 (Admin)     │ admin_ali, admin_zeynep, admin_burak │${NC}"
echo -e "${CYAN}  │  VLAN 20 (Employee)  │ emp_mehmet, emp_ayse, emp_fatma,     │${NC}"
echo -e "${CYAN}  │                      │ emp_can, emp_deniz                   │${NC}"
echo -e "${CYAN}  │  VLAN 30 (Guest)     │ guest_user, guest_ahmet,            │${NC}"
echo -e "${CYAN}  │                      │ guest_elif, guest_tamir             │${NC}"
echo -e "${CYAN}  │  VLAN 40 (IoT)       │ 8 MAC cihaz (yazıcı, kamera,       │${NC}"
echo -e "${CYAN}  │                      │ sensör, kilit, ekran, AP)           │${NC}"
echo -e "${CYAN}  └──────────────────────────────────────────────────────────────┘${NC}"
echo ""
echo -e "${GREEN}  Tüm senaryolar tamamlandı!${NC}"
echo ""
echo -e "${YELLOW}  Kullanışlı komutlar:${NC}"
echo -e "    curl http://localhost:8000/users | python3 -m json.tool"
echo -e "    curl http://localhost:8000/sessions/active | python3 -m json.tool"
echo -e "    curl http://localhost:8000/health | python3 -m json.tool"
echo ""
