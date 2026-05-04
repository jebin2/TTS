#!/bin/bash

mkdir -p static/js

# Tailwind CSS CDN play bundle (v3 with forms + container-queries plugins)
# cdn.tailwindcss.com may fail DNS on some networks — resolve via known IP
echo "Downloading tailwind.min.js..."
curl -L --resolve "cdn.tailwindcss.com:443:104.26.2.143" \
    "https://cdn.tailwindcss.com/?plugins=forms,container-queries" \
    -o static/js/tailwind.min.js

echo "Done. Files saved to static/js/"
