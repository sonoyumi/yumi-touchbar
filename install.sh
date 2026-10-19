#!/bin/bash
# yumi-touchbar: install touchbard (pinned upstream commit + the patches from patches/) with the yumi style,
# its layers, plugins and helper scripts for the current user. Run as your user; sudo is asked only for the
# system part, which is touchbard's own installer (manifest-based, rolls back to tiny-dfr if the daemon does not come up).
#   ./install.sh                 build, install, switch ~/.config/touchbar/config.toml to the yumi style (old one is backed up)
#   ./install.sh --keep-config   the same, but leave your current config.toml as it is (the style goes to styles/yumi.toml)
# Undo: ./uninstall.sh
set -euo pipefail

Y=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
COMMIT=1b29141c2a592b81c14f05b8590c34ce78bb99cf
SRC=${TOUCHBARD_SRC:-$HOME/.cache/yumi-touchbar/touchbard}
CFG=$HOME/.config/touchbar
LIST=$HOME/.local/share/yumi-touchbar/installed.txt
KEEP=0
[ "${1:-}" = "--keep-config" ] && KEEP=1

say() { printf '\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m   %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" != 0 ] || die "run as your user, not with sudo (sudo is asked for the system part)"
for t in git cargo gcc python3; do command -v $t >/dev/null || die "missing $t (pacman -S git rust gcc python)"; done
python3 -c 'import cairo' 2>/dev/null || die "missing pycairo (pacman -S python-cairo)"
python3 -c 'import gi; gi.require_version("Rsvg", "2.0"); from gi.repository import Rsvg' 2>/dev/null ||
	die "missing python-gobject + librsvg (pacman -S python-gobject librsvg)"
for f in "Noto Serif" "Noto Serif CJK JP" "JetBrainsMono Nerd Font"; do
	fc-list : family 2>/dev/null | grep -F "$f" >/dev/null || warn "font \"$f\" not found - the bar will fall back to another font (pacman -S noto-fonts noto-fonts-cjk ttf-jetbrains-mono-nerd)"
done

say "1/5 touchbard source at ${COMMIT:0:7} + patches"
if [ ! -d "$SRC/.git" ]; then
	mkdir -p "$(dirname "$SRC")"
	git clone -q https://github.com/0800tim/touchbard "$SRC"
fi
git -C "$SRC" fetch -q origin
git -C "$SRC" checkout -q -f "$COMMIT"
git -C "$SRC" clean -q -fd -e daemon/target
for p in "$Y"/patches/*.patch; do
	git -C "$SRC" apply --whitespace=nowarn "$p" || die "patch $(basename "$p") does not apply"
	echo "   applied $(basename "$p")"
done
# the seal for touchid_style = "seal" - the daemon reads it from /usr/local/share/touchbar (it cannot see ~)
install -Dm644 "$Y/share/hanko.png" "$SRC/share/touchbar/hanko.png"

say "2/5 Build (cargo test + release)"
# explicit gcc: some setups shadow `cc` in PATH with something that is not a compiler
export CC=gcc RUSTFLAGS="${RUSTFLAGS:-} -C linker=gcc"
(cd "$SRC/daemon" && cargo test --release -q 2>&1 | grep -E '^test result|FAILED|panicked' && cargo build --release -q)
[ -x "$SRC/daemon/target/release/touchbard" ] || die "build failed"

say "3/5 System part (touchbard's own installer, sudo)"
sudo "$SRC/system/install.sh"

say "4/5 Style, plugins, scripts -> ~/.config/touchbar, ~/.local/bin"
mkdir -p "$CFG/plugins" "$CFG/styles" "$HOME/.local/bin" "$(dirname "$LIST")"
: >"$LIST.new"
put() {   # put SRC DEST - copy, keeping a backup of a different existing file
	if [ -e "$2" ] && ! cmp -s "$1" "$2" 2>/dev/null && [ ! -L "$2" ]; then
		cp -a "$2" "$2.bak-yumi-touchbar"
	fi
	rm -f "$2"
	cp -a "$1" "$2"
	echo "$2" >>"$LIST.new"
}
for d in "$Y"/plugins/*/; do
	n=$(basename "$d"); mkdir -p "$CFG/plugins/$n"
	(cd "$d" && find . -type f -o -type l) | while read -r f; do
		mkdir -p "$CFG/plugins/$n/$(dirname "$f")"
		put "$d$f" "$CFG/plugins/$n/${f#./}"
	done
done
for f in "$Y"/plugins/*.py; do put "$f" "$CFG/plugins/$(basename "$f")"; done
put "$Y/styles/yumi.toml" "$CFG/styles/yumi.toml"
[ "$KEEP" = 1 ] || put "$Y/styles/yumi.toml" "$CFG/config.toml"
for f in "$Y"/bin/*; do put "$f" "$HOME/.local/bin/$(basename "$f")"; done
mv "$LIST.new" "$LIST"

say "5/5 Session agent"
install -Dm644 "$SRC/system/touchbar-agent.service" "$HOME/.config/systemd/user/touchbar-agent.service"
systemctl --user daemon-reload
systemctl --user enable --now touchbar-agent
systemctl --user restart touchbar-agent
# colours from the wallpaper accent of yumi-rice, if it is there (otherwise the agent keeps its default theme)
"$HOME/.local/bin/yumi-touchbar-theme" || true

say "Done. Layers: yumi-touchbar-layer   Undo: ./uninstall.sh"
if [ "$KEEP" = 1 ]; then echo "   Your config.toml was kept; the yumi style is in $CFG/styles/yumi.toml"; fi
