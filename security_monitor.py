"""Read-only health checks for the registered antivirus and Windows Firewall."""
import json
import subprocess
import time

_SECURITY_QUERY = r"""
$ErrorActionPreference = 'Stop'
$antiviruses = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | ForEach-Object { $_.displayName })
$norton = Get-Service -Name 'NortonSecurity' -ErrorAction SilentlyContinue
$profiles = @(Get-NetFirewallProfile | ForEach-Object { [pscustomobject]@{ Name = $_.Name; Enabled = [bool]$_.Enabled } })
[pscustomobject]@{
    AntivirusProducts = $antiviruses
    NortonService = if ($norton) { $norton.Status.ToString() } else { 'NotFound' }
    FirewallProfiles = $profiles
} | ConvertTo-Json -Depth 4 -Compress
"""


def get_security_status():
    """Return the registered antivirus, Norton service, and firewall state.

    This reports security posture only. It does not scan, quarantine, delete,
    or terminate anything.
    """
    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            _SECURITY_QUERY,
        ],
        capture_output=True,
        check=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    data = json.loads(result.stdout)
    antivirus_products = data.get("AntivirusProducts") or []
    firewall_profiles = data.get("FirewallProfiles") or []
    if isinstance(antivirus_products, str):
        antivirus_products = [antivirus_products]
    if isinstance(firewall_profiles, dict):
        firewall_profiles = [firewall_profiles]

    return {
        "antivirus_products": antivirus_products,
        "norton_service": data.get("NortonService", "Unknown"),
        "firewall_profiles": firewall_profiles,
    }


def security_warnings(status):
    warnings = []
    antivirus_products = status["antivirus_products"]
    norton_registered = any("norton" in name.lower() for name in antivirus_products)

    if not antivirus_products:
        warnings.append("O Windows não informa um antivírus registrado.")
    elif not norton_registered:
        warnings.append("O Norton não aparece registrado no Windows Security Center.")
    elif status["norton_service"] != "Running":
        warnings.append("O serviço do Norton não está em execução.")

    disabled_profiles = [
        profile.get("Name", "desconhecido")
        for profile in status["firewall_profiles"]
        if not profile.get("Enabled", False)
    ]
    if disabled_profiles:
        warnings.append("O Firewall está desligado em um ou mais perfis.")
    elif not status["firewall_profiles"]:
        warnings.append("Não foi possível confirmar os perfis do Firewall.")

    return warnings


def describe_security_status(status):
    antivirus_products = status["antivirus_products"]
    antivirus_text = ", ".join(antivirus_products) if antivirus_products else "nenhum registrado"
    firewall_profiles = status["firewall_profiles"]
    enabled_profiles = [
        profile.get("Name", "desconhecido")
        for profile in firewall_profiles
        if profile.get("Enabled", False)
    ]
    firewall_text = ", ".join(enabled_profiles) if enabled_profiles else "nenhum perfil confirmado"

    details = [f"Antivírus registrado: {antivirus_text}."]
    if any("norton" in name.lower() for name in antivirus_products):
        details.append(f"Serviço Norton: {status['norton_service']}.")
    details.append(f"Perfis de Firewall ativos: {firewall_text}.")
    details.append("Isto verifica o estado da proteção, não detecta nem exclui ameaças.")
    return " ".join(details)


def open_norton():
    subprocess.Popen(
        ["explorer.exe", "shell:AppsFolder\\NortonLifeLock.Norton Security"],
        close_fds=True,
    )


def security_monitor_loop(check_interval, on_alert):
    previous_warnings = None
    previous_error = None

    while True:
        try:
            status = get_security_status()
            warnings = security_warnings(status)
            current_warnings = tuple(warnings)

            if current_warnings != previous_warnings:
                if warnings:
                    on_alert(" ".join(warnings))
                elif previous_warnings:
                    on_alert("Norton e Firewall voltaram ao estado esperado.")
                previous_warnings = current_warnings
            previous_error = None
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
            if str(error) != previous_error:
                print("Security status check unavailable:", error)
                previous_error = str(error)

        time.sleep(check_interval)