#!/usr/bin/env sh
set -eu

for tool in node npx javac java g++ go rustc dotnet; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "Missing required runtime toolchain: $tool" >&2
    exit 1
  }
done

node_major="$(node --version | sed 's/^v//' | cut -d. -f1)"
[ "$node_major" -ge 20 ] || {
  echo "Node.js 20+ LTS is required; found $(node --version)" >&2
  exit 1
}

java_major="$(javac -version 2>&1 | awk '{print $2}' | cut -d. -f1)"
[ "$java_major" -ge 17 ] || {
  echo "JDK 17+ is required; found $(javac -version 2>&1)" >&2
  exit 1
}

dotnet --list-sdks | grep -Eq '^8\.' || {
  echo ".NET 8 SDK is required" >&2
  exit 1
}

node --version
npx --version
javac --version
java --version
g++ --version
go version
rustc --version
dotnet --version
