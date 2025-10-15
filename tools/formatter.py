import os
import shutil
import re
import yaml
from datetime import datetime

# Base paths
base_path = "../"
processed_path = os.path.join(base_path, "processed")

# Load output_path from config
config_path = os.path.join(base_path, "config.yml")
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
output_path = config['output_path']

default_image = os.path.join(base_path, r"assets\default.jpg")

# Get all markdown files in processed folder
files = [f for f in os.listdir(processed_path) if f.endswith('.md')]

for filename in files:
    file_path = os.path.join(processed_path, filename)
    
    folder_name = filename.replace('.md', '')
    title = folder_name
    
    # Read original content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Get current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Create frontmatter
    frontmatter = f"""---
title: '{title}'
publishDate: {current_date}
description: 'TODO'
tags:
  - TODO
language: 'English'
heroImage: {{ src: './default.jpg', color: '#D58388' }}
---

"""
    
    # Combine frontmatter with content
    new_content = frontmatter + content
    
    # Create new folder
    new_folder = os.path.join(output_path, folder_name)
    os.makedirs(new_folder, exist_ok=True)
    
    # Write updated file to new folder
    new_file_path = os.path.join(new_folder, filename)
    with open(new_file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    # Copy default.jpg to new folder
    new_image_path = os.path.join(new_folder, "default.jpg")
    shutil.copy2(default_image, new_image_path)
    
    print(f"Processed {filename} -> {folder_name}/")

print("\nAll files processed successfully!")
print(f"Total files processed: {len(files)}")
