import urllib.request, re, os

OUT = "assets/icons"
os.makedirs(OUT, exist_ok=True)

GROUPS = {
    "💻 Languages": ["java", "js", "html"],
    "🧩 Frameworks & Libraries": ["spring", "hibernate"],
    "☁️ Cloud, DevOps & Infrastructure": ["kafka", "kubernetes", "docker", "jenkins", "linux", "aws"],
    "🗄️ Databases": ["oracle", "postgres", "mysql"],
    "📊 Monitoring": ["grafana", "prometheus"],
    "🧪 Testing & API": ["postman"],
    "🤖 GenAI": ["githubcopilot", "cursor"],
    "🧰 IDEs & Tools": ["idea", "vscode", "git", "jira", "confluence"],
}

def build(inner, delay):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="-8 -14 272 284">
<style>
  .icon {{ transform-origin: 128px 128px; animation: float 2.6s ease-in-out {delay}s infinite; }}
  .glow {{ animation: glow 2.6s ease-in-out {delay}s infinite; }}
  @keyframes float {{
    0%,100% {{ transform: translateY(0) scale(1); }}
    50% {{ transform: translateY(-10px) scale(1.08); }}
  }}
  @keyframes glow {{
    0%,100% {{ filter: drop-shadow(0 0 0 rgba(88,166,255,0)); }}
    50% {{ filter: drop-shadow(0 6px 10px rgba(88,166,255,.55)); }}
  }}
</style>
<g class="glow"><g class="icon">{inner}</g></g>
</svg>'''

html = []
i = 0
for title, names in GROUPS.items():
    html.append(f"### {title}\n<p>")
    for n in names:
        try:
            svg = urllib.request.urlopen(f"https://skillicons.dev/icons?i={n}").read().decode().strip()
            inner = re.sub(r"^<svg[^>]*>|</svg>\s*$", "", svg)
            with open(f"{OUT}/{n}.svg", "w", encoding="utf-8") as f:
                f.write(build(inner, round((i % 6) * 0.25, 2)))
            html.append(f'  <img src="assets/icons/{n}.svg" width="72" alt="{n}"/>')
            i += 1
        except Exception as e:
            print("skipped", n, e)
    html.append("</p>\n")

open("icons_snippet.html", "w", encoding="utf-8").write("\n".join(html))
print("Done")
