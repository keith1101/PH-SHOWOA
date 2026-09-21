#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$project_dir/build/classes"
find "$project_dir/src/main/java" -name '*.java' -print > "$project_dir/build/sources.txt"
if [ "${1:-}" = "--test" ]; then
  find "$project_dir/src/test/java" -name '*.java' -print >> "$project_dir/build/sources.txt"
fi
sed 's/.*/"&"/' "$project_dir/build/sources.txt" > "$project_dir/build/javac.args"
javac -encoding UTF-8 -source 8 -target 8 -Xlint:all -d "$project_dir/build/classes" @"$project_dir/build/javac.args"
if [ "${1:-}" = "--test" ]; then
  java -Xmx1g -ea -cp "$project_dir/build/classes" phshowoa.RegressionTests "$project_dir"
fi
