#!/bin/bash
# Dev helper: create N test players and save their session cookies.
# Usage: ./scripts/dev-players.sh [count] [prefix]
#   count = number of players (default 4)
#   prefix = name prefix (default Player)

COUNT=${1:-4}
PREFIX=${2:-Player}
API="http://localhost:8080/api/auth/debug/login"
COOKIE_DIR="/tmp/taupe-test-cookies"
mkdir -p "$COOKIE_DIR"

echo "Creating $COUNT test player(s)..."
rm -f "$COOKIE_DIR"/*.txt

i=1
while [ $i -le $COUNT ]; do
  NAME="${PREFIX}${i}"
  COOKIE_FILE="$COOKIE_DIR/player${i}.txt"
  RESP=$(curl -s -X POST "$API" -H "Content-Type: application/json" -d "{\"display_name\":\"$NAME\"}" -c "$COOKIE_FILE")
  echo "  $NAME → $(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['id'][:8])")"
  i=$((i + 1))
done

echo ""
echo "Cookies stored in $COOKIE_DIR/"
echo "Use with curl: curl -b $COOKIE_DIR/player1.txt http://localhost:8080/api/me"
echo ""
echo "To test in browser, open one tab per player URL:"
echo "  /dev/login  → manually log in as each name"
echo "  or use different browser profiles with cookies imported"
