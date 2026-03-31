import os
import yaml
import re

SKILLS_DIR = r"c:\Users\thaku\OneDrive\Desktop\my project\browser\clawbot\skills"
OUT_FILE = r"c:\Users\thaku\OneDrive\Desktop\my project\browser\clawbot\SKILLS_DIRECTORY.md"

def extract_frontmatter(content):
    match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1))
        except:
            return {}
    return {}

def generate_markdown():
    skills = []
    
    # Read core skills
    if os.path.exists(SKILLS_DIR):
        for folder in os.listdir(SKILLS_DIR):
            skill_md = os.path.join(SKILLS_DIR, folder, "SKILL.md")
            if os.path.exists(skill_md):
                with open(skill_md, "r", encoding="utf-8") as f:
                    data = extract_frontmatter(f.read())
                    if data:
                        name = data.get("name", folder)
                        desc = data.get("description", "No description provided.")
                        skills.append((name, desc))
                        
    # Read .claude skills (like gitnexus)
    claude_dir = r"c:\Users\thaku\OneDrive\Desktop\my project\browser\clawbot\.claude\skills"
    if os.path.exists(claude_dir):
        for folder in os.listdir(claude_dir):
            if folder == "gitnexus":
                # Gitnexus has nested folders
                for sub in os.listdir(os.path.join(claude_dir, folder)):
                    skill_md = os.path.join(claude_dir, folder, sub, "SKILL.md")
                    if os.path.exists(skill_md):
                        with open(skill_md, "r", encoding="utf-8") as f:
                            data = extract_frontmatter(f.read())
                            if data:
                                name = data.get("name", sub)
                                desc = data.get("description", "No description provided.")
                                skills.append((name, desc))
    
    skills.sort(key=lambda x: x[0])
    
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 🧰 ClawBot Complete Skills Directory\n\n")
        f.write("This document lists all the specialized skills installed in ClawBot. You can request any of these skills organically during chat.\n\n")
        f.write("| Skill Name | What it does | Example Prompt |\n")
        f.write("| --- | --- | --- |\n")
        for name, desc in skills:
            # Clean up newlines in description
            desc_clean = desc.replace('\n', ' ').strip()
            # Generate a generic prompt based on the name if no specific prompt is obvious
            prompt = f"`Use the {name} skill to...`"
            if "Example:" in desc_clean:
                # Try to extract the example if provided in description
                ex_match = re.search(r'Example[s]?:\s*(.*)', desc_clean, re.IGNORECASE)
                if ex_match:
                    prompt = f"`{ex_match.group(1).split('.')[0].strip()}`"
                    desc_clean = re.sub(r'Example[s]?:\s*.*', '', desc_clean, flags=re.IGNORECASE).strip()
            
            f.write(f"| **`{name}`** | {desc_clean} | {prompt} |\n")

    print(f"Directory generated at {OUT_FILE} with {len(skills)} skills.")

if __name__ == '__main__':
    generate_markdown()
