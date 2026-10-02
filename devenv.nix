{ pkgs, lib, config, ... }:

{
  packages = [

  (pkgs.ollama.override { acceleration = "cuda"; })
  pkgs.tesseract
  pkgs.libpq
  ];

  languages.python = {
    enable = true;
    package = pkgs.python312;
    venv.enable = true;
    uv.enable = true;
    venv.requirements = ''
      --extra-index-url https://download.pytorch.org/whl/cu121
      torch
      torchvision
      torchaudio
      mcp
      ollama
      gradio
      fastapi
      fastapi-cli
      uvicorn
      qdrant-client
      pymupdf
      pymupdf4llm
      docling
      openai
      python-dotenv
      fastembed
      FlagEmbedding
      markdown_chunker
      chonkie
      psycopg[binary,pool]
      requests
    '';
  };
  
  env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
    pkgs.stdenv.cc.cc.lib
    pkgs.zlib
    pkgs.glib
    pkgs.libGL
    pkgs.xorg.libxcb
    pkgs.xorg.libX11
    pkgs.xorg.libXext
    pkgs.xorg.libXrender
    pkgs.xorg.libICE
    pkgs.xorg.libSM
  ]+ ":/run/opengl-driver/lib";

  env = {
    OLLAMA_HOST = "http://127.0.0.1:11434";
    CHROMA_DATA_DIR = "/home/flkr/.chroma";
    UV_INDEX_STRATEGY = "unsafe-best-match";
    UV_HTTP_TIMEOUT = "1200";    
    UV_CONCURRENT_DOWNLOADS = "20";
  };

  processes.qdrant.exec = ''
    podman run --rm \
      -p 6333:6333 -p 6334:6334 \
      --ulimit nofile=10000:10000 \
      -v $(pwd)/qdrant_storage:/qdrant/storage \
      docker.io/qdrant/qdrant
  '';

  enterShell = ''
    mkdir -p "$CHROMA_DATA_DIR"
    echo "Python: $(python --version)"
    echo "Ollama: $(ollama --version 2>/dev/null || echo 'installed; run ollama serve')"
    echo "Start Ollama with: ollama serve"
    echo "Run FastAPI with: uvicorn app:app --reload"
    echo "Run Streamlit with: streamlit run app.py"
    echo "Run Gradio with: python app.py"
    echo "Postgres is available on localhost:${toString config.services.postgres.port}"
  '';

    services.postgres = {
      enable = true;
      listen_addresses = "localhost";
      settings.port = lib.mkDefault 5432;
      port = 5432;
      initialDatabases = [ { name = "AnadoluIsuzuDB"; } ];
    };
}
