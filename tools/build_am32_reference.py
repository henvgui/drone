"""Build the unmodified AM32 v2.21 G071 reference with an installed GNU toolchain.

Mirrors the upstream Makefile source sets and compiler flags, without downloading
or running upstream setup scripts. Outputs are audit artifacts, not board firmware.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--linker", type=Path)
    parser.add_argument("--name", default="upstream")
    parser.add_argument("--low-address-flash", action="store_true",
                        help="Allow the upstream bootloader-info read through the Cortex-M low Flash alias with GCC 12")
    args = parser.parse_args()
    source = ROOT / "references/AM32-v2.21"
    output = ROOT / "build/am32-audit" / args.name
    output.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which("arm-none-eabi-gcc")
    if not compiler:
        raise SystemExit("arm-none-eabi-gcc is required")
    actual_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if actual_revision != "6b3ef3d15228e8d70244bd6e3bd87c7eac939d6f":
        raise SystemExit("Reference checkout is not the audited v2.21 commit")
    groups = ["Src", "Mcu/g071/Startup", "Mcu/g071/Drivers/STM32G0xx_HAL_Driver/Src", "Mcu/g071/Src"]
    sources = [str(p.relative_to(source)).replace("\\", "/")
               for folder in groups for p in sorted((source / folder).iterdir())
               if p.suffix in (".c", ".s")]
    includes = ["Inc", "Mcu/g071/Inc", "Mcu/g071/Drivers/STM32G0xx_HAL_Driver/Inc",
                "Mcu/g071/Drivers/CMSIS/Include", "Mcu/g071/Drivers/CMSIS/Device/ST/STM32G0xx/Include"]
    defines = ["GEN_128K_G071", 'AM32_MCU="G071"', "HSE_VALUE=8000000", "STM32G071xx",
               "HSE_STARTUP_TIMEOUT=100", "LSE_STARTUP_TIMEOUT=5000", "LSE_VALUE=32768",
               "DATA_CACHE_ENABLE=1", "INSTRUCTION_CACHE_ENABLE=0", "VDD_VALUE=3300",
               "LSI_VALUE=32000", "HSI_VALUE=16000000", "USE_FULL_LL_DRIVER", "PREFETCH_ENABLE=1"]
    linker = args.linker.resolve() if args.linker else source / "Mcu/g071/STM32G071GBUX_FLASH.ld"
    elf = output / "GEN_128K_G071.elf"
    command = [compiler, "-mcpu=cortex-m0", "-mthumb", "-fsingle-precision-constant",
               "-fomit-frame-pointer", "-ffast-math", "-g3", "-O3", "-ffunction-sections",
               "--specs=nosys.specs", "-Wall", "-Wundef", "-Wextra", "-Werror",
               "-Wno-unused-parameter", "-Wno-stringop-truncation"]
    command += ["-I" + p for p in includes] + ["-D" + d for d in defines]
    if args.low_address_flash:
        command += ["--param=min-pagesize=0"]
    command += ["--specs=nano.specs", "-Wl,--gc-sections", "-Wl,--print-memory-usage",
                "-Wl,-Map=" + str(output / "GEN_128K_G071.map"), "-T" + str(linker),
                "-o", str(elf)] + sources + ["-lnosys"]
    manifest = {"target": "GEN_128K_G071", "reference_commit": actual_revision,
                "linker": str(linker), "command": command, "source_count": len(sources),
                "low_address_flash_compiler_option": args.low_address_flash,
                "board_ready": False}
    result = subprocess.run(command, cwd=source, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output / "build.log").write_text(result.stdout, encoding="utf-8")
    manifest["exit_code"] = result.returncode
    if result.returncode == 0:
        objdump = shutil.which("arm-none-eabi-objdump")
        if objdump:
            sections = subprocess.check_output([objdump, "-h", str(elf)], text=True)
            (output / "sections.txt").write_text(sections, encoding="utf-8")
            print(sections)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(result.stdout)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
