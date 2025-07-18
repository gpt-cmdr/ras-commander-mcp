"""
This script generates a comprehensive summary knowledge base for the ras-commander library.
It processes the project files and creates the following output file:

ras-commander_fullrepo.txt:
   A comprehensive summary of all relevant project files, including their content
   and structure. This file provides an overview of the entire codebase, including
   all files and folders except those specified in OMIT_FOLDERS and OMIT_FILES.

The output file is generated in the 'llm_knowledge_bases' directory and serves
as a complete reference for AI assistants or developers who need a full overview
of the project structure and content.
"""

import os
from pathlib import Path
import re
import json
from typing import Dict, Any, List, Union

# Configuration
OMIT_FOLDERS = [
    "testdata", ".ai_tools", ".git", ".gemini", ".claude", "ArcHydro Default Layers", "Images", "Bald Eagle Creek", "__pycache__", ".git", ".github", "tests", "docs", "library_assistant", "__pycache__", ".conda", "workspace"
    "build", "dist", "ras_commander.egg-info", "venv", "ras_commander.egg-info", "log_folder", "logs", ".venv",
    "example_projects", "llm_knowledge_bases", "misc", "ai_tools", "FEMA_BLE_Models", "hdf_example_data", "ras_example_categories", "data", "apidocs", "build", "dist", "ras_commander.egg-info", "venv", "log_folder", "logs",
]
OMIT_FILES = [
    ".lyrx", ".png",".hdf", ".pyc", ".pyo", ".pyd", ".dll", ".so", ".dylib", ".exe",
    ".bat", ".sh", ".log", ".tmp", ".bak", ".swp", "uv.lock",
    ".DS_Store", "Thumbs.db", "example_projects.zip",
    "Example_Projects_6_6.zip", "example_projects.ipynb", "11_Using_RasExamples.ipynb", 
    "future_dev_roadmap.ipynb", "structures_attributes.csv", "example_projects.csv",
    ".ico", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".mp4", ".avi", ".mov", ".mp3", ".wav", ".m4a", ".m4v", ".ogg", ".webm"
]
SUMMARY_OUTPUT_DIR = "llm_knowledge_bases"
SCRIPT_NAME = Path(__file__).name

# Recursively delete all __pycache__ folders and their contents
for folder in Path(__file__).parent.parent.rglob("__pycache__"):
    if folder.is_dir():
        print(f"Deleting __pycache__ folder and contents: {folder}")
        try:
            # Recursively delete all subfolders and files
            for item in folder.rglob("*"):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()
            # Delete the empty __pycache__ folder itself
            folder.rmdir()
            print(f"Successfully deleted {folder} and all contents")
        except Exception as e:
            print(f"Error deleting {folder}: {e}")

def ensure_output_dir(base_path: Path) -> Path:
    output_dir = base_path / SUMMARY_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory ensured to exist: {output_dir}")
    return output_dir

def should_omit(filepath: Path) -> bool:
    if filepath.name == SCRIPT_NAME:
        return True
    if any(omit_folder in filepath.parts for omit_folder in OMIT_FOLDERS):
        return True
    if any(filepath.suffix == ext or filepath.name == ext for ext in OMIT_FILES):
        return True
    return False

def process_notebook_content(filepath: Path) -> str:
    """
    Process a Jupyter notebook to remove images and truncate dataframe outputs.
    
    Args:
        filepath: Path to the notebook file
        
    Returns:
        Processed notebook content as a string
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        # Process each cell
        for cell in notebook.get('cells', []):
            if cell.get('cell_type') == 'code':
                # Process outputs
                if 'outputs' in cell:
                    cell['outputs'] = clean_notebook_outputs(cell['outputs'])
        
        # Convert back to string with indentation for readability
        return json.dumps(notebook, indent=2)
    
    except Exception as e:
        print(f"Error processing notebook {filepath}: {e}")
        # Fall back to original content
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

def process_notebook_no_outputs(filepath: Path) -> str:
    """
    Process a Jupyter notebook to completely remove all outputs.
    
    Args:
        filepath: Path to the notebook file
        
    Returns:
        Processed notebook content as a string with all outputs removed
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        # Process each cell
        for cell in notebook.get('cells', []):
            if cell.get('cell_type') == 'code':
                # Remove all outputs
                cell['outputs'] = []
                # Reset execution count
                if 'execution_count' in cell:
                    cell['execution_count'] = None
        
        # Convert back to string with indentation for readability
        return json.dumps(notebook, indent=2)
    
    except Exception as e:
        print(f"Error processing notebook {filepath}: {e}")
        # Fall back to original content
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

def save_cleaned_notebooks(summarize_subfolder: Path, output_dir: Path) -> None:
    """
    Save cleaned versions of all notebooks to a separate subfolder.
    All notebooks will be placed directly in the root of example_notebooks_cleaned.
    If the cleaned notebook is >100KB, remove all outputs.
    """
    cleaned_notebooks_dir = output_dir / "example_notebooks_cleaned"
    cleaned_notebooks_dir.mkdir(parents=True, exist_ok=True)
    print(f"Creating cleaned notebooks directory: {cleaned_notebooks_dir}")
    
    # Find all notebooks
    notebooks = list(summarize_subfolder.rglob('*.ipynb'))
    
    for notebook_path in notebooks:
        if should_omit(notebook_path):
            continue
        try:
            # Process the notebook to clean outputs
            with open(notebook_path, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
            # Process each cell
            for cell in notebook.get('cells', []):
                if cell.get('cell_type') == 'code':
                    if 'outputs' in cell:
                        cell['outputs'] = clean_notebook_outputs(cell['outputs'])
            # Use only the filename for the target path (no subdirectories)
            target_path = cleaned_notebooks_dir / notebook_path.name
            # Overwrite any existing file with the same name
            if target_path.exists():
                target_path.unlink()
            # Save the cleaned notebook
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(notebook, f, indent=2)
            # Check file size; if >100KB, remove all outputs and save again
            if target_path.stat().st_size > 100 * 1024:
                print(f"Notebook {notebook_path} cleaned version >100KB, removing all outputs.")
                no_output_content = process_notebook_no_outputs(notebook_path)
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(no_output_content)
            print(f"Saved cleaned notebook: {target_path}")
        except Exception as e:
            print(f"Error processing notebook {notebook_path}: {e}")

def clean_notebook_outputs(outputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean cell outputs by removing images and truncating dataframes.
    
    Args:
        outputs: List of cell output dictionaries
        
    Returns:
        Cleaned outputs
    """
    cleaned_outputs = []
    
    for output in outputs:
        output_type = output.get('output_type', '')
        
        # Handle display_data outputs (images, HTML, etc.)
        if output_type == 'display_data':
            new_output = output.copy()
            
            # Remove image data (png, jpeg, etc.)
            if 'data' in new_output:
                # Remove all image formats
                for img_format in ['image/png', 'image/jpeg', 'image/svg+xml']:
                    if img_format in new_output['data']:
                        del new_output['data'][img_format]
                
                # Check if this might be a DataFrame or other rich HTML display
                if 'text/html' in new_output['data']:
                    html_content = new_output['data']['text/html']
                    new_output['data']['text/html'] = process_html_output(html_content)
                
                # If data dict is now empty or only has empty values, add a placeholder
                if not new_output['data'] or all(not v for v in new_output['data'].values()):
                    new_output['data']['text/plain'] = '[Image or rich display removed during preprocessing]'
            
            cleaned_outputs.append(new_output)
            continue
        
        # Handle execute_result outputs (including dataframes, xarrays)
        elif output_type == 'execute_result':
            new_output = output.copy()
            
            if 'data' in new_output:
                # Process HTML content (DataFrames, xarray objects)
                if 'text/html' in new_output['data']:
                    html_content = new_output['data']['text/html']
                    new_output['data']['text/html'] = process_html_output(html_content)
                
                # Process plain text output
                if 'text/plain' in new_output['data']:
                    text_content = new_output['data']['text/plain']
                    new_output['data']['text/plain'] = process_text_output(text_content)
            
            cleaned_outputs.append(new_output)
        
        # Handle stream outputs (stdout/stderr)
        elif output_type == 'stream':
            new_output = output.copy()
            
            # Truncate very long text outputs
            if 'text' in new_output and isinstance(new_output['text'], str):
                text = new_output['text']
                lines = text.splitlines()
                
                # Truncate if more than 20 lines
                if len(lines) > 20:
                    truncated_text = '\n'.join(lines[:10]) + '\n...\n' + '\n'.join(lines[-5:])
                    truncated_text += f"\n[Output truncated, {len(lines)} lines total]"
                    new_output['text'] = truncated_text
            
            cleaned_outputs.append(new_output)
        
        # Handle error outputs
        elif output_type == 'error':
            # Keep error outputs as they are (they're usually important)
            cleaned_outputs.append(output)
        
        else:
            # For other output types, include them as is
            cleaned_outputs.append(output)
    
    return cleaned_outputs

def process_html_output(html_content: str) -> str:
    """
    Process HTML output content to truncate and simplify it.
    
    Args:
        html_content: HTML content to process
        
    Returns:
        Processed HTML content
    """
    # Handle case where html_content is not a string
    if not isinstance(html_content, str):
        try:
            # Try to convert to string if possible
            html_content = str(html_content)
        except Exception:
            # If conversion fails, return a placeholder
            return "<div><pre>[Non-string HTML content removed during preprocessing]</pre></div>"
    
    # Check for DataFrame HTML pattern
    if '<table' in html_content and ('dataframe' in html_content or '<style' in html_content):
        return truncate_dataframe_html(html_content)
    
    # Check for xarray HTML pattern
    elif 'xarray' in html_content.lower() and ('<table' in html_content or '<div' in html_content):
        # Extract xarray type
        xarray_type = "xarray.Dataset" if "xarray.Dataset" in html_content else "xarray.DataArray"
        
        # Extract dimensions if possible
        dims_match = re.search(r'Dimensions:(.+?)<', html_content, re.DOTALL)
        dims_info = dims_match.group(1).strip() if dims_match else "Unknown dimensions"
        
        # Return simplified version
        return f"""<div><pre>{xarray_type} with {dims_info}
[Full xarray output truncated during preprocessing]</pre></div>"""
    
    # Check for other kinds of rich HTML content (plots, widgets, etc.)
    elif any(pattern in html_content.lower() for pattern in 
            ['<svg', 'matplotlib', 'bokeh', 'plotly', 'widget', 'vis']):
        return """<div><pre>[Visualization or interactive content removed during preprocessing]</pre></div>"""
    
    # Other HTML content - truncate if very long
    elif len(html_content) > 5000:
        return f"""<div><pre>[Long HTML output truncated: {len(html_content)} characters]</pre></div>"""
    
    # Otherwise, keep the HTML content as is
    return html_content

def process_text_output(text_content: str) -> str:
    """
    Process text output content to truncate and simplify it.
    
    Args:
        text_content: Text content to process
        
    Returns:
        Processed text content
    """
    # Handle case where text_content is not a string
    if not isinstance(text_content, str):
        try:
            # Try to convert to string if possible
            text_content = str(text_content)
        except Exception:
            # If conversion fails, return a placeholder
            return "[Non-string text content removed during preprocessing]"
    
    # Check for DataFrame text representation
    if ('DataFrame' in text_content and '\n' in text_content) or \
       ('[' in text_content and ']' in text_content and '\n' in text_content):
        
        # Count the number of lines
        lines = text_content.splitlines()
        if len(lines) > 10:
            # Simple truncation for DataFrames
            return "[DataFrame output truncated, showing preview only]\n" + '\n'.join(lines[:7]) + '\n...'
    
    # Check for xarray text representation
    elif 'xarray.Dataset' in text_content or 'xarray.DataArray' in text_content:
        # Extract xarray type
        xarray_type = "xarray.Dataset" if "xarray.Dataset" in text_content else "xarray.DataArray"
        
        # Extract dimensions if possible
        dims_match = re.search(r'Dimensions:(.+?)\n', text_content)
        dims_info = dims_match.group(1).strip() if dims_match else "Unknown dimensions"
        
        # Abbreviated description
        return f"{xarray_type} with {dims_info}\n[Full xarray output truncated during preprocessing]"
    
    # Truncate general long text outputs
    elif len(text_content) > 2000:
        lines = text_content.splitlines()
        if len(lines) > 20:
            return '\n'.join(lines[:10]) + '\n...\n' + '\n'.join(lines[-5:]) + \
                   f"\n[Output truncated, {len(lines)} lines total]"
        else:
            return text_content[:1000] + f"\n...\n[Output truncated, {len(text_content)} characters total]"
    
    # Otherwise, keep the text as is
    return text_content

def truncate_dataframe_html(html_content: str) -> str:
    """
    Truncate an HTML dataframe to show only the header and a few rows.
    
    Args:
        html_content: HTML content containing a dataframe
        
    Returns:
        Truncated HTML content
    """
    # Handle case where html_content is not a string
    if not isinstance(html_content, str):
        try:
            # Try to convert to string if possible
            html_content = str(html_content)
        except Exception:
            # If conversion fails, return a placeholder
            return "<div><pre>[Non-string HTML DataFrame content removed during preprocessing]</pre></div>"
    
    # Keep the styling information
    style_match = re.search(r'<style.*?</style>', html_content, re.DOTALL)
    style_section = style_match.group(0) if style_match else ""
    
    # Find the table
    table_match = re.search(r'<table.*?</table>', html_content, re.DOTALL)
    if not table_match:
        return html_content  # Not a table, return as is
    
    table_content = table_match.group(0)
    
    # Extract the header
    header_match = re.search(r'<thead.*?</thead>', table_content, re.DOTALL)
    header_section = header_match.group(0) if header_match else ""
    
    # Extract the first few data rows (up to 5)
    body_match = re.search(r'<tbody.*?</tbody>', table_content, re.DOTALL)
    if body_match:
        body_content = body_match.group(0)
        row_matches = re.findall(r'<tr>.*?</tr>', body_content, re.DOTALL)
        
        max_rows = min(5, len(row_matches))
        first_rows = ''.join(row_matches[:max_rows])
        
        # Construct a new tbody with limited rows plus truncation message
        truncated_body = f"<tbody>\n    {first_rows}\n    <tr><td colspan=\"100%\" style=\"text-align:center\">[... additional rows truncated ...]</td></tr>\n  </tbody>"
    else:
        truncated_body = "<tbody><tr><td>[No data rows]</td></tr></tbody>"
    
    # Reconstruct the table
    table_start_match = re.search(r'<table.*?>', table_content)
    table_start = table_start_match.group(0) if table_start_match else "<table>"
    
    truncated_table = f"{table_start}\n  {header_section}\n  {truncated_body}\n</table>"
    
    # Put it all together
    return f"<div>\n{style_section}\n{truncated_table}\n</div>"

def read_file_contents(filepath: Path) -> str:
    try:
        # Process Jupyter notebooks specially
        if filepath.suffix.lower() == '.ipynb':
            print(f"Processing notebook: {filepath}")
            # For full repo, truncate outputs
            return process_notebook_content(filepath)
        
        # For XML files, remove binary image data and <Binary><Thumbnail><Data ...>...</Data></Thumbnail></Binary> blocks
        if filepath.suffix.lower() == '.xml':
            with open(filepath, 'r', encoding='utf-8') as infile:
                content = infile.read()
                # Remove binary image data between <Enclosure> tags
                content = re.sub(r'<Enclosure[^>]*>.*?</Enclosure>', '', content, flags=re.DOTALL)
                # Remove <Binary><Thumbnail><Data ...>...</Data></Thumbnail></Binary> blocks
                content = re.sub(
                    r'<Binary>\s*<Thumbnail>\s*<Data[^>]*>.*?</Data>\s*</Thumbnail>\s*</Binary>',
                    '',
                    content,
                    flags=re.DOTALL | re.IGNORECASE
                )
                print(f"Reading and cleaning XML content of file: {filepath}")
                return content
        
        # Regular file reading for other files
        with open(filepath, 'r', encoding='utf-8') as infile:
            content = infile.read()
            print(f"Reading content of file: {filepath}")
    except UnicodeDecodeError:
        with open(filepath, 'rb') as infile:
            content = infile.read().decode('utf-8', errors='ignore')
            print(f"Reading and converting content of file: {filepath}")
    return content

def build_project_tree(filepaths: List[Path], base_path: Path) -> str:
    """
    Build a project structure tree as a string, given a list of filepaths.
    Only includes files actually included in the knowledge base.
    """
    from collections import defaultdict
    
    # Create a tree structure using nested dictionaries
    tree: Dict[str, Any] = {}
    
    for path in filepaths:
        rel_parts = Path(path).relative_to(base_path).parts
        current_level = tree
        
        # Navigate through the directory structure
        for part in rel_parts[:-1]:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]
        
        # Add the file at the final level
        current_level[rel_parts[-1]] = "FILE"
    
    def render(subtree: Dict[str, Any], prefix: str = "") -> List[str]:
        lines = []
        items = sorted(subtree.items())
        
        for i, (name, child) in enumerate(items):
            connector = "└── " if i == len(items) - 1 else "├── "
            lines.append(f"{prefix}{connector}{name}")
            
            if isinstance(child, dict):
                extension = "    " if i == len(items) - 1 else "│   "
                lines.extend(render(child, prefix + extension))
        
        return lines
    
    return '\n'.join(render(tree))

def write_project_tree_and_content(outfile, filepaths: List[Path], base_path: Path, cleaned_notebooks_dir: Path) -> None:
    """
    Write the project structure tree and then the content for each file.
    """
    tree_str = build_project_tree(filepaths, base_path)
    outfile.write("Project Structure (files included):\n")
    outfile.write(tree_str + "\n\n")
    
    for filepath in filepaths:
        outfile.write(f"File: {filepath}\n")
        outfile.write("="*50 + "\n")
        
        if filepath.suffix.lower() == '.ipynb':
            # Use cleaned notebook if available
            cleaned_notebook_path = cleaned_notebooks_dir / filepath.name
            if cleaned_notebook_path.exists():
                with open(cleaned_notebook_path, 'r', encoding='utf-8') as cleanfile:
                    content = cleanfile.read()
                outfile.write(content)
                outfile.write("\n" + "="*50 + "\n\n")
                continue
        
        content = read_file_contents(filepath)
        outfile.write(content)
        outfile.write("\n" + "="*50 + "\n\n")

def generate_full_summary(summarize_subfolder: Path, output_dir: Path) -> None:
    output_file_name = f"{summarize_subfolder.name}_fullrepo.txt"
    output_file_path = output_dir / output_file_name
    print(f"Generating Full Summary: {output_file_path}")
    
    cleaned_notebooks_dir = output_dir / "example_notebooks_cleaned"
    
    filepaths = []
    for filepath in summarize_subfolder.rglob('*'):
        if should_omit(filepath):
            continue
        if filepath.is_file():
            filepaths.append(filepath)
    
    with open(output_file_path, 'w', encoding='utf-8') as outfile:
        write_project_tree_and_content(outfile, filepaths, summarize_subfolder, cleaned_notebooks_dir)
    
    print(f"Full summary created at '{output_file_path}'")

def main() -> None:
    # Get the name of this script
    this_script = SCRIPT_NAME
    print(f"Script name: {this_script}")

    # Define the subfolder to summarize (parent of the script's parent)
    summarize_subfolder = Path(__file__).parent.parent
    print(f"Subfolder to summarize: {summarize_subfolder}")

    # Ensure the output directory exists
    output_dir = ensure_output_dir(Path(__file__).parent)

    # Delete all existing files in the output directory and its subfolders
    for file in output_dir.rglob('*'):
        if file.is_file():
            file.unlink()
    
    # Save cleaned notebooks to a separate subfolder
    save_cleaned_notebooks(summarize_subfolder, output_dir)

    # Generate the full repository summary
    generate_full_summary(summarize_subfolder, output_dir)

    print(f"Full repository summary has been generated in '{output_dir}'")

if __name__ == "__main__":
    main()
