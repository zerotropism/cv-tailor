from pathlib import Path


def load_resumes(data_dir="../data"):
    """Load all .txt resumes from a directory.

    Args:
        data_dir (str): Path to the directory containing .txt files.
    Returns:
        dict: keys are filenames without the .txt extension, values are the
            file contents as strings.
    """
    resumes = {}
    data_path = Path(__file__).parent / data_dir

    if not data_path.exists():
        return resumes

    for file_path in data_path.iterdir():
        if file_path.suffix == ".txt":
            resumes[file_path.stem] = file_path.read_text(encoding="utf-8")

    return resumes
