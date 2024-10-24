import subprocess
import sys


def update_packages(requirements_file):
    try:
        import pipreqs  # type: ignore
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pipreqs"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"Updating {requirements_file}...")
    subprocess.run(['pipreqs', '.', '--force'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with open(requirements_file, 'r') as file:
        lines = file.readlines()

    unique_lines = list(dict.fromkeys(lines))

    with open(requirements_file, 'w') as file:
        file.writelines(unique_lines)

    print("Updating project...")
    subprocess.run(['pip', 'install', '-r', requirements_file],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"Verifing {requirements_file}...")
    subprocess.run(['pip', 'check'])


if __name__ == "__main__":
    update_packages('requirements.txt')
