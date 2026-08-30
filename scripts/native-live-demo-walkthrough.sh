#!/bin/sh
set -eu



read -r -p "Press Enter to continue..."

base_url=${1:-http://127.0.0.1:7393}

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 2
  }
}

require curl
require jq

status() {
  curl --fail --silent --show-error "$base_url/api/live"
}

wait_for_result() {
  before=$1
  while :; do
    body=$(status)
    serial=$(printf '%s' "$body" | jq -r '.conditionSerial')
    state=$(printf '%s' "$body" | jq -r '.state')
    case "$state" in
      Checking|Staged|Migrating|WaitingForQuiescence) ;;
      *)
        if [ "$serial" -gt "$before" ]; then
          printf '%s\n' "$body"
          return
        fi
        ;;
    esac
  done
}

submit() {

  label=$1
  expected=$2
  before=$(status | jq -r '.conditionSerial')

  echo
  echo "===== $label: submitted source ====="
  source=$(sed -e 's/[[:space:]]*$//')
  printf '%s\n' "$source"

  curl --fail --silent --show-error \
    -X POST \
    -H 'Content-Type: text/plain' \
    --data-binary "$source" \
    "$base_url/api/live/edit" >/dev/null

  body=$(wait_for_result "$before")
  echo "===== $label: terminal state ====="
  printf '%s\n' "$body" | jq .

  actual=$(printf '%s' "$body" | jq -r '.result')
  if [ "$actual" -ne "$expected" ]; then
    echo "$label: expected result $expected, got $actual" >&2
    exit 1
  fi

  if [ "$actual" -eq 0 ]; then
    curl --fail --silent --show-error \
      "$base_url/api/native-demo/frame" >/dev/null
    echo "$label: frame rendered"
  fi
}

initial=$(status)
echo "===== initial state ====="
printf '%s\n' "$initial" | jq .

initial_epoch=$(printf '%s' "$initial" | jq -r '.jitEpoch')
initial_pending=$(printf '%s' "$initial" | jq -r '.pending')
if [ "$initial_epoch" -ne 1 ] || [ -n "$initial_pending" ]; then
  echo "walkthrough requires a fresh server at epoch 1 with no pending source" >&2
  exit 2
fi

# curl --fail --silent --show-error \
#   -X POST "$base_url/api/native-demo/pause" >/dev/null

read -r -p "Press Enter to continue..."

submit 'step 1' 0 <<'EOF'
(defn radius [(p Particle)] (-> i64)
  14)
EOF
read -r -p "Press Enter to continue..."

submit 'step 2' 0 <<'EOF'
(defstruct Particle
  [(x i64) (y i64) (vx i64) (vy i64)
   (hue i64 20)
   (visible bool true)])

(defn tint [(p Particle)] (-> i64)
  (if (.visible p)
      (+ (.hue p) (/ (.x p) 3))
      0))
EOF

read -r -p "Press Enter to continue..."

submit 'step 3 (expected rejection)' 1 <<'EOF'
(defsum Visibility (Hidden) (Visible))

(defstruct Particle
  [(x i64) (y i64) (vx i64) (vy i64)
   (hue i64 20)
   (visible Visibility)])
EOF

read -r -p "Press Enter to continue..."

submit 'step 4 (repair)' 0 <<'EOF'
(defsum Visibility (Hidden) (Visible))

(defstruct Particle
  [(x i64) (y i64) (vx i64) (vy i64)
   (hue i64 20)
   (visible Visibility (Visible))])

(migrate Particle visible old
  (if old (Visible) (Hidden)))

(defn tint [(p Particle)] (-> i64)
  (match (.visible p)
    (Hidden [] 0)
    (Visible [] (+ (.hue p) (/ (.x p) 3)))))

(defn advance [(p Particle)] (-> Particle)
  (let [(mut nx) (+ (.x p) (.vx p))
        (mut ny) (+ (.y p) (.vy p))
        (mut nvx) (.vx p)
        (mut nvy) (.vy p)]
    (when (< nx 14) (store! nx 14) (store! nvx (- 0 nvx)))
    (when (> nx 626) (store! nx 626) (store! nvx (- 0 nvx)))
    (when (< ny 14) (store! ny 14) (store! nvy (- 0 nvy)))
    (when (> ny 386) (store! ny 386) (store! nvy (- 0 nvy)))
    (Particle :x nx :y ny :vx nvx :vy nvy
              :hue (.hue p) :visible (.visible p))))
EOF

read -r -p "Press Enter to continue..."

submit 'step 5' 0 <<'EOF'
(defsum Kind (Dot) (Ring))

(defn kind-of [(p Particle)] (-> Kind)
  (if (> (.x p) 320) (Ring) (Dot)))

(defn kind-code [(p Particle)] (-> i64)
  (match (kind-of p)
    (Dot [] 0)
    (Ring [] 1)))
EOF

read -r -p "Press Enter to continue..."

submit 'step 6 (expected rejection; stale kind-code is explicit)' 1 <<'EOF'
(defsum Kind (Dot) (Ring) (Bar))

(defn kind-of [(p Particle)] (-> Kind)
  (if (> (.x p) 430)
      (Bar)
      (if (> (.x p) 320) (Ring) (Dot))))

(defn kind-code [(p Particle)] (-> i64)
  (match (kind-of p)
    (Dot [] 0)
    (Ring [] 1)))
EOF

read -r -p "Press Enter to continue..."
submit 'step 7 (three-arm repair)' 0 <<'EOF'
(defn kind-code [(p Particle)] (-> i64)
  (match (kind-of p)
    (Dot [] 0)
    (Ring [] 1)
    (Bar [] 2)))
EOF
read -r -p "Press Enter to continue..."

# curl --fail --silent --show-error \
#   -X POST "$base_url/api/native-demo/run" >/dev/null
# curl --fail --silent --show-error \
#   "$base_url/api/native-demo/frame" >/dev/null

echo
echo '===== walkthrough completed ====='
status | jq .
