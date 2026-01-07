
import os
import base64

# Files to bundle
FILES = [
    "strategic_bot.py",
    "config.py",
    "strategic_state.json",
    "verify_deployment.py",
    "strategies/echo.py",
    "strategies/nia.py",
    "strategies/aamr.py",
    "strategies/base.py",
    "strategies/__init__.py",
    "screener.py",
    "dashboard.py",
    ".env.example"
]


def generate_installers():
    # PART 1: CORE (Small, Critical)
    core_files = ["strategic_bot.py", "config.py", "strategic_state.json", "verify_deployment.py", ".env.example"]
    create_script("PASTE_1_CORE.sh", core_files, 
                  header=["mkdir -p strategies"], 
                  footer=["echo '✅ PART 1 COMPLETE'"])

    # PART 2: STRATEGIES (Medium)
    strat_files = [
        "strategies/echo.py", "strategies/nia.py", 
        "strategies/aamr.py", "strategies/base.py", 
        "strategies/__init__.py"
    ]
    create_script("PASTE_2_STRATS.sh", strat_files, 
                  footer=["echo '✅ PART 2 COMPLETE'"])

    # PART 3: SCREENER & DASHBOARD (Large)
    extra_files = ["screener.py", "dashboard.py"]
    create_script("PASTE_3_EXTRAS.sh", extra_files, 
                  footer=["echo '✅ PART 3 COMPLETE'", 
                          "echo '-----------------------------------'",
                          "echo '🏁 INSTALLATION FINISHED'", 
                          "echo 'Next: nano .env', 'python3 verify_deployment.py --vps'"])

def create_script(filename, file_list, header=[], footer=[]):
    script_lines = ["#!/bin/bash", "echo '🦅 Installing part: " + filename + "'"]
    script_lines.extend(header)
    
    for relative_path in file_list:
        if os.path.exists(relative_path):
            with open(relative_path, "rb") as f:
                content = f.read()
                b64 = base64.b64encode(content).decode('utf-8')
            
            # Ensure directory exists for nested files
            directory = os.path.dirname(relative_path)
            if directory:
                script_lines.append(f"mkdir -p {directory}")
                
            script_lines.append(f"echo 'Restoring {relative_path}...'")
            script_lines.append(f"base64 -d > {relative_path} << 'EOF'")
            script_lines.append(b64)
            script_lines.append("EOF")
        else:
            print(f"Warning: {relative_path} not found.")

    script_lines.extend(footer)
    
    with open(filename, "w", encoding='utf-8') as f:
        f.write("\n".join(script_lines))
    print(f"Generated {filename}")

if __name__ == "__main__":
    generate_installers()
