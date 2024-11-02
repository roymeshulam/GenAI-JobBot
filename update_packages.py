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

    packages = {}
    for line in lines:
        if '==' in line:
            pkg, ver = line.strip().split('==')
            if pkg in packages:
                # Keep the latest version
                if ver > packages[pkg]:
                    packages[pkg] = ver
            else:
                packages[pkg] = ver

    with open(requirements_file, 'w') as file:
        for pkg, ver in packages.items():
            file.write(f'{pkg}=={ver}\n')

    print("Updating project...")
    subprocess.run(['pip', 'install', '-r', requirements_file],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"Verifing {requirements_file}...")
    subprocess.run(['pip', 'check'])


if __name__ == "__main__":
    update_packages('requirements.txt')
