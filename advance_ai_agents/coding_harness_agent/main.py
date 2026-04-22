import inspect
import json
import os

# import openai
# from dotenv import load_dotenv
from pathlib import Path
from typing import Any, Dict, List, Tuple

YOU_COLOR = "\u001b[94m"
ASSISTANT_COLOR = "\u001b[93m"
RESET_COLOR = "\u001b[0m"

prompt = ""


def abs_path_tool(path_str: str) -> Path:
    """
    file.py -> /Users/you/project/file.py
    """
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def all_files_tool(folder_path: str) -> Dict[str, Any]:
    """
    Get all the files in a folder provided by the user.
    :param folder_path: The path to the folder to get the files from.
    :return: A dictionary with the type of the tool call and the list of files.
    """
    print(f"Getting all files in folder: {folder_path}")
    path = abs_path_tool(folder_path)
    # if not path.exists():
    #     return {
    #         "type": "all_files",
    #         "error": f"Folder not found: {path}"
    #     }
    all_files = []

    for file in path.iterdir():
        if file.is_file():
            print(f"{YOU_COLOR}Found file:{RESET_COLOR} {file.name}")
            all_files.append({
                "filename": file.name,
                "type": "file"
            })
        elif file.is_dir():
            print(f"{YOU_COLOR}Found folder:{RESET_COLOR} {file.name}")
            all_files.append({
                "filename": file.name,
                "type": "dir"
            })

    print(f"{YOU_COLOR}Found {len(all_files)} files in folder:{RESET_COLOR} {path}")
    return {"type": "all_files","folder_path": str(folder_path), "files": all_files}


def file_read_tool(file_path: str) -> Dict[str, Any]:
    """
    Get the full content of a file provided by the user.
    :param file_path: The path to the file to read.
    :return: A dictionary with the type of the tool call and the content of the file.
    """
    path = abs_path_tool(file_path)
    print(f"Reading file: {path}")
    if not path.exists():
        return {"type": "file_read", "error": f"File not found: {path}"}

    with open(path, "r") as file:
        content = file.read()
        return {"type": "file_read", "content": content}


def file_edit_tool(file_path: str, old_content: str, new_content: str) -> Dict[str, Any]:
    """
    Edit a file provided by the user.
    :param file_path: The path to the file to edit.
    :param content: The new content of the file.
    :return: A dictionary with the type of the tool call and the content of the file.
    """
    print(f"Editing file: {file_path}")
    path = abs_path_tool(file_path)
    if not path.exists():
        return {"type": "file_edit", "error": f"File not found: {path}"}

    if old_content == "":
        with open(path, "w") as file:
            file.write(new_content)
            return {"type": "file_edit", "content": new_content}
    else:
        with open(path, "r") as file:
            content = file.read()
            if content == old_content:
                with open(path, "w") as file:
                    file.write(new_content)


def main():
    print("Hello from coding-harness-agent!")


if __name__ == "__main__":
    # main()
    print(file_read_tool("./main.py")["content"])
