# Learn Docker by deploying PruInsight

This guide is a **hands-on Docker course** using **this project**.  
Do the steps in order. Each step has: **what to type**, **what it means**, and **why it matters**.

---

## 0. Mental model (read this first)

| Concept | Everyday analogy | In this project |
|---------|------------------|-----------------|
| **Image** | A frozen recipe / install CD of your app | Built from `Dockerfile` → `pruinsight-agent:latest` |
| **Container** | A running instance of that recipe | One process serving Streamlit on port 8501 |
| **Dockerfile** | Instructions to build the image | Install Python deps, copy code, start Streamlit |
| **docker compose** | A remote control for multi-step run | `docker-compose.yml` builds + maps ports + loads `.env` |
| **Volume** | A shared folder (host ↔ container) | We don’t need one for v1 (code is inside the image) |
| **Port mapping** | House number → apartment number | `8501:8501` = your browser → container Streamlit |
| **env / secrets** | Keys you don’t print on the recipe | `.env` injected at **run** time, not baked into image |

```
Your PC (Host)
   │
   │  browser → http://localhost:8501
   │
   ▼
┌─────────────────────────────┐
│  Container: pruinsight      │
│  Streamlit :8501            │
│  Python + your code         │
│  ENV: GROQ_API_KEY, …       │
└─────────────────────────────┘
         ▲
         │ built from
         │
┌─────────────────────────────┐
│  Image: pruinsight-agent    │
│  (Dockerfile + requirements)│
└─────────────────────────────┘
```

---

## 1. Install Docker Desktop (Windows)

1. Download **Docker Desktop for Windows**: https://www.docker.com/products/docker-desktop/  
2. Install, reboot if asked.  
3. Start **Docker Desktop** and wait until it says **Running**.  
4. Open **PowerShell** or **Git Bash** and check:

```bash
docker --version
docker compose version
```

You should see version numbers, not “command not found”.

**Learn:** Docker Engine runs Linux containers. On Windows, Docker Desktop uses a small Linux VM (WSL2). You still type `docker` on Windows; it talks to that engine.

**If `docker` fails:** open Docker Desktop UI → Settings → ensure WSL2 backend is enabled.

---

## 2. Project files we added for Docker

| File | Purpose |
|------|---------|
| `Dockerfile` | Recipe to build the image |
| `docker-compose.yml` | Easy `up` / `down` with ports + `.env` |
| `.dockerignore` | Files **not** copied into the image (like `.gitignore`) |
| `.streamlit/config.toml` | Streamlit listens on `0.0.0.0` inside the container |

Open `Dockerfile` and read the comments — each line is one layer of the recipe.

---

## 3. Prepare secrets (do not put keys in the Dockerfile)

In the project root you already have `.env`:

```env
GROQ_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
```

**Learn:**  
- `.dockerignore` excludes `.env` from the **image** (good — keys not in the image layers).  
- `docker-compose.yml` uses `env_file: .env` so keys exist only in the **running container**.

Never commit `.env`. Never write `ENV GROQ_API_KEY=gsk_...` in the Dockerfile.

---

## 4. First command: build the image (manual Docker)

Go to the project folder:

```bash
cd "C:/Users/divvy/OneDrive/Desktop/Agentic AI Learning/pruinsight-agent"
```

Build:

```bash
docker build -t pruinsight-agent:latest .
```

| Piece | Meaning |
|-------|---------|
| `docker build` | Build an image |
| `-t pruinsight-agent:latest` | Tag (name:tag) so you can find it later |
| `.` | Build **context** = current folder (sent to Docker; filtered by `.dockerignore`) |

This will take a few minutes the first time (downloads Python base image + pip packages).

Check images:

```bash
docker images
```

You should see `pruinsight-agent`.

**Learn — layers:** Docker caches steps. If you only change Python code, it often reuses the “pip install” layer and rebuilds faster. That’s why `requirements.txt` is copied **before** `COPY . .` in the Dockerfile.

---

## 5. Run a container from the image (manual)

```bash
docker run --rm -p 8501:8501 --env-file .env --name pruinsight pruinsight-agent:latest
```

| Flag | Meaning |
|------|---------|
| `--rm` | Delete container when it stops (keeps your machine clean) |
| `-p 8501:8501` | Map host port → container port |
| `--env-file .env` | Inject environment variables |
| `--name pruinsight` | Friendly name for `docker ps` / `docker logs` |

Open browser: **http://localhost:8501**

Stop: press `Ctrl+C` in the terminal.

**Learn — ports:** Inside the container Streamlit listens on `0.0.0.0:8501`. Without `-p`, only processes *inside* the container network could reach it. `-p` publishes it to your Windows host.

---

## 6. Easier path: Docker Compose (recommended daily use)

From the project root:

```bash
docker compose up --build
```

| Piece | Meaning |
|-------|---------|
| `docker compose up` | Create network + start services in `docker-compose.yml` |
| `--build` | Rebuild image if Dockerfile/code changed |

Open: **http://localhost:8501**

Run in background (detached):

```bash
docker compose up --build -d
```

See logs:

```bash
docker compose logs -f
```

Stop and remove containers:

```bash
docker compose down
```

**Learn:** Compose is YAML automation for the same things as long `docker run` commands. For one service it’s convenience; for multi-service apps (app + redis + db) it becomes essential.

---

## 7. Everyday inspection commands (practice these)

```bash
# Running containers
docker ps

# All containers (including stopped)
docker ps -a

# Logs from our compose service
docker compose logs -f pruinsight

# Shell inside the running container (explore the Linux filesystem)
docker compose exec pruinsight bash
# then try:  ls /app   |   env | grep API   |   exit

# Resource usage
docker stats

# Remove unused images/build cache (when disk fills up)
docker system prune
```

**Learn:** `exec` runs a command *in* a running container. `run` starts a **new** container.

---

## 8. CLI mode inside Docker (optional)

Streamlit is the default `CMD`. To run the CLI once without changing the image:

```bash
docker compose run --rm pruinsight \
  python main.py "HDFC Bank for MF desk" -s HDFCBANK
```

Or with an interactive override:

```bash
docker run --rm --env-file .env pruinsight-agent:latest \
  python main.py "Reliance outlook" -s RELIANCE -v
```

**Learn:** Anything after the image name **replaces** the default `CMD` for that run.

---

## 9. Change code → rebuild loop

1. Edit Python files on your PC.  
2. Rebuild and restart:

```bash
docker compose up --build -d
```

3. Hard-refresh the browser.

**Learn:** Code is **copied into the image** at build time (simple model). Code changes need rebuild.  
(Later you’ll learn **bind mounts** so local files appear live inside the container without rebuild — great for dev.)

### Bonus: live-reload style mount (optional learning)

```bash
docker run --rm -p 8501:8501 --env-file .env \
  -v "${PWD}:/app" \
  pruinsight-agent:latest
```

On PowerShell you may need:

```powershell
docker run --rm -p 8501:8501 --env-file .env -v ${PWD}:/app pruinsight-agent:latest
```

**Warning:** mounting over `/app` can hide packages if not careful; for learning it’s OK after a normal build once.

---

## 10. Troubleshooting

| Problem | What to try |
|---------|-------------|
| Port already in use | Change host port: `"8502:8501"` in compose, open `localhost:8502` |
| App says missing API keys | Check `.env` exists next to `docker-compose.yml`; recreate: `docker compose up -d --force-recreate` |
| Build fails on pip | Check network; retry `docker compose build --no-cache` |
| Container exits immediately | `docker compose logs pruinsight` |
| Browser can’t connect | Ensure Docker Desktop running; `docker ps` shows `0.0.0.0:8501->8501` |
| Slow first build | Normal — base image + pip; later builds use cache |

---

## 11. What NOT to do (security basics)

1. Don’t `COPY .env` into the image.  
2. Don’t print secrets in logs or Dockerfiles.  
3. Don’t push images containing keys to Docker Hub.  
4. For cloud deploy later: use platform secrets (ECS/Fly/Railway/Render env vars), not files committed to git.

---

## 12. Mini glossary cheat sheet

| Command | One-line meaning |
|---------|------------------|
| `docker build` | Create image from Dockerfile |
| `docker run` | Start a container from an image |
| `docker ps` | List running containers |
| `docker logs` | Show container stdout/stderr |
| `docker exec` | Run command inside running container |
| `docker stop` / `docker rm` | Stop / delete container |
| `docker rmi` | Delete image |
| `docker compose up` | Start stack from YAML |
| `docker compose down` | Stop stack, remove containers/network |

---

## 13. Suggested learning path (after this works)

1. **Today:** `compose up`, open UI, generate one note.  
2. **Tomorrow:** `exec` into the container, `ls /app`, understand filesystem.  
3. **Next:** Add a bind mount for live dev.  
4. **Later:** Multi-stage Dockerfile to shrink image size.  
5. **Later:** Deploy image to a cloud VM or PaaS with HTTPS.

---

## 14. Quick reference card

```bash
# From project root — all you need day-to-day
docker compose up --build        # foreground
docker compose up --build -d     # background
docker compose logs -f           # watch logs
docker compose down              # stop

# Browser
http://localhost:8501
```

You now have a real app packaged the way production teams package Python services.  
When this works, say if you want **step 2 of Docker learning**: multi-stage builds, smaller images, or cloud deploy.
