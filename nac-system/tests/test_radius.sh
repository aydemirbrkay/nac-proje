#!/bin/bash
# ============================================================
# NAC Sistemi — FreeRADIUS Üzerinden RADIUS Protokol Testleri
# ============================================================
# Bu script RADIUS protokolünü doğrudan test eder.
# FreeRADIUS konteyneri içinden çalıştırılmalıdır:
#
#   docker exec -it nac-freeradius bash
#   bash /tests/test_radius.sh
#
# Veya dışarıdan:
#   docker exec nac-freeradius bash /tests/test_radius.sh
#
# NOT: radtest ve radclient FreeRADIUS ile birlikte gelir.
# ============================================================

echo "═══════════════════════════════════════"
echo "  RADIUS Protokol Testleri"
echo "═══════════════════════════════════════"
echo ""

SECRET="testing123"
RADIUS_HOST="127.0.0.1"

# ── 1. PAP Authentication — radtest ──
echo "── 1. PAP Authentication (radtest) ──"
echo ""

echo "→ Admin kullanıcı testi:"
radtest admin_ali Admin1234! $RADIUS_HOST 0 $SECRET
echo ""

echo "→ Employee kullanıcı testi:"
radtest emp_mehmet Emp1234! $RADIUS_HOST 0 $SECRET
echo ""

echo "→ Yanlış şifre testi (reject bekleniyor):"
radtest admin_ali yanlis_sifre $RADIUS_HOST 0 $SECRET
echo ""

# ── 2. MAB Authentication — radclient ──
echo "── 2. MAB Authentication (radclient) ──"
echo ""

echo "→ Kayıtlı cihaz (Yazıcı) testi:"
echo "User-Name=AA:BB:CC:DD:EE:01,Calling-Station-Id=AA:BB:CC:DD:EE:01,User-Password=AA:BB:CC:DD:EE:01" \
    | radclient $RADIUS_HOST auth $SECRET
echo ""

echo "→ Bilinmeyen cihaz testi (guest VLAN bekleniyor):"
echo "User-Name=FF:FF:FF:FF:FF:FF,Calling-Station-Id=FF:FF:FF:FF:FF:FF,User-Password=FF:FF:FF:FF:FF:FF" \
    | radclient $RADIUS_HOST auth $SECRET
echo ""

# ── 3. Accounting — radclient ──
echo "── 3. Accounting (radclient) ──"
echo ""

SESSION_ID="radius-test-$(date +%s)"

echo "→ Accounting Start:"
echo "User-Name=admin_ali,Acct-Status-Type=Start,Acct-Session-Id=$SESSION_ID,NAS-IP-Address=192.168.1.1,NAS-Port-Id=GigabitEthernet0/1" \
    | radclient $RADIUS_HOST acct $SECRET
echo ""

sleep 2

echo "→ Accounting Interim-Update:"
echo "User-Name=admin_ali,Acct-Status-Type=Interim-Update,Acct-Session-Id=$SESSION_ID,NAS-IP-Address=192.168.1.1,Acct-Session-Time=120,Acct-Input-Octets=50000,Acct-Output-Octets=200000" \
    | radclient $RADIUS_HOST acct $SECRET
echo ""

sleep 2

echo "→ Accounting Stop:"
echo "User-Name=admin_ali,Acct-Status-Type=Stop,Acct-Session-Id=$SESSION_ID,NAS-IP-Address=192.168.1.1,Acct-Session-Time=300,Acct-Input-Octets=100000,Acct-Output-Octets=500000,Acct-Terminate-Cause=User-Request" \
    | radclient $RADIUS_HOST acct $SECRET
echo ""

echo "═══════════════════════════════════════"
echo "  RADIUS testleri tamamlandı"
echo "═══════════════════════════════════════"
