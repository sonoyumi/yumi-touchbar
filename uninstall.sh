#!/bin/bash
# yumi-touchbar: undo install.sh. touchbard's own uninstaller puts tiny-dfr back (it removes only files
# from its manifest whose checksums still match); then the files this repo copied for your user are removed
# and any *.bak-yumi-touchbar backups are put back (your previous config.toml too, if install.sh replaced it).
set -uo pipefail

SRC=${TOUCHBARD_SRC:-$HOME/.cache/yumi-touchbar/touchbard}
LIST=$HOME/.local/share/yumi-touchbar/installed.txt

say() { printf '\033[1;32m==> %s\033[0m\n' "$*"; }

[ "$(id -u)" != 0 ] || { echo "run as your user, not with sudo"; exit 1; }

say "Session agent"
systemctl --user disable --now touchbar-agent 2>/dev/null
rm -f "$HOME/.config/systemd/user/touchbar-agent.service"
systemctl --user daemon-reload 2>/dev/null

say "System part (touchbard's uninstaller, sudo) - back to tiny-dfr"
if [ -x "$SRC/system/uninstall.sh" ]; then
	sudo "$SRC/system/uninstall.sh"
else
	echo "   $SRC/system/uninstall.sh not found - run touchbard's system/uninstall.sh by hand"
fi

say "Files copied for your user"
if [ -s "$LIST" ]; then
	while read -r f; do
		rm -f "$f"
		[ -e "$f.bak-yumi-touchbar" ] && mv "$f.bak-yumi-touchbar" "$f"
	done <"$LIST"
	find "$HOME/.config/touchbar/plugins" -mindepth 1 -type d -empty -delete 2>/dev/null
	rm -f "$LIST"
fi
say "Done. The build cache is in $(dirname "$SRC") - remove it by hand if you like"
