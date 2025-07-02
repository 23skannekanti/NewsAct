import os
from datetime import datetime

def save_output(company: str, label: str, content: str, folder="MCPdatalogs"):
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_company = company.replace(" ", "_")
    dir_path = os.path.join(folder, safe_company)
    os.makedirs(dir_path, exist_ok=True)

    file_path = os.path.join(dir_path, f"{date_str}_{label}.txt")

    with open(file_path, "w") as f:
        f.write(content)

    print(f"✅ Saved {label} to {file_path}")
