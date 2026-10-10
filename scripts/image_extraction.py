"""Extract all audit inputs without creating the privileged console device."""
import subprocess


def extract_for_audit(tool, image, destination):
    # Exclude only this device node. All other extraction errors remain fatal.
    subprocess.run([str(tool), '-d', str(destination), '-excludes',
                    str(image), 'dev/console'], check=True)
