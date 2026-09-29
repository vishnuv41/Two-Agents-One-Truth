#!/bin/sh
# usage: sh omega/install.sh /path/to/Omega   (then run Omega with TWOAGENTS_HOME exported)
set -e
OMEGA="$1"; HERE="$(cd "$(dirname "$0")/.." && pwd)"
cp -r "$HERE/omega/plugins/twoagents" "$OMEGA/plugins/"
printf '\n- name: twoagents\n  loader: metta\n  location: "{REPO}/plugins/twoagents"\n' >> "$OMEGA/config/plugins.yaml"
echo "Installed. Run: export TWOAGENTS_HOME=$HERE ; then start Omega and ask it to resolve a conflict (it should emit (negotiate \"crop\"))."
