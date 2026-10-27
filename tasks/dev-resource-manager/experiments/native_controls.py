"""Build an isolated GUI bundle; a command-line observer launches it in background."""
import plistlib
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).with_suffix(".swift").resolve()
with tempfile.TemporaryDirectory(prefix="svc-prep-native-") as directory:
    root = Path(directory)
    bundle = root / "SVCPreparationProbe.app"
    executable = bundle / "Contents/MacOS/SVCPreparationProbe"
    executable.parent.mkdir(parents=True)
    info = {
        "CFBundlePackageType": "APPL", "CFBundleExecutable": executable.name,
        "CFBundleIdentifier": "dev.svc.preparation.native-controls", "CFBundleName": "SVC Preparation Probe",
        "LSMinimumSystemVersion": "14.0", "NSPrincipalClass": "NSApplication", "LSUIElement": True,
    }
    (bundle / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
    subprocess.run(["swiftc", "-swift-version", "6", str(source), "-o", str(executable)], check=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(bundle)], check=True, capture_output=True)
    result = subprocess.run([str(executable), "--monitor", str(bundle), str(root / "result.json")],
                            capture_output=True, text=True, timeout=30)
    suffix = "result.json" if result.returncode == 0 else "failure.txt"
    evidence = result.stdout if result.returncode == 0 else result.stdout + "\n" + result.stderr
    (source.parent / ("native-controls-" + suffix)).write_text(evidence)
    print(evidence[:6000])
    if result.returncode != 0:
        raise SystemExit(result.returncode)
