from __future__ import annotations
import asyncio
import os
import subprocess
import plistlib
from pathlib import Path
from datetime import time
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Launchd 스케줄러 (macOS)
# ──────────────────────────────────────────────

@dataclass
class LaunchdJob:
    """launchd 작업 정의"""
    label: str
    program: str
    args: list[str]
    start_calendar: dict  # {"Hour": 8, "Minute": 0}
    working_directory: str
    environment: dict = None
    run_at_load: bool = False
    keep_alive: bool = False
    standard_out_path: str = None
    standard_error_path: str = None


class LaunchdScheduler:
    """macOS launchd 스케줄러 관리"""
    
    LAUNCHD_DIR = Path.home() / "Library" / "LaunchAgents"
    
    # 작업 정의
    JOBS = {
        "aikorea24-carousel": LaunchdJob(
            label="com.aikorea24.carousel",
            program="/usr/bin/python3",
            args=["-m", "scripts.threads.v3.auto_poster.main", "--mode", "carousel"],
            start_calendar={"Hour": 8, "Minute": 0},
            working_directory="/Users/twinssn/Projects/aikorea24",
            environment={
                "PYTHONPATH": "/Users/twinssn/Projects/aikorea24",
                "PYTHONUNBUFFERED": "1",
            },
            standard_out_path="/Users/twinssn/Projects/aikorea24/logs/carousel.log",
            standard_error_path="/Users/twinssn/Projects/aikorea24/logs/carousel_error.log",
        ),
        "aikorea24-reels": LaunchdJob(
            label="com.aikorea24.reels",
            program="/usr/bin/python3",
            args=["-m", "scripts.threads.v3.auto_poster.main", "--mode", "reels"],
            start_calendar={"Hour": 19, "Minute": 0},
            working_directory="/Users/twinssn/Projects/aikorea24",
            environment={
                "PYTHONPATH": "/Users/twinssn/Projects/aikorea24",
                "PYTHONUNBUFFERED": "1",
            },
            standard_out_path="/Users/twinssn/Projects/aikorea24/logs/reels.log",
            standard_error_path="/Users/twinssn/Projects/aikorea24/logs/reels_error.log",
        ),
    }
    
    def __init__(self):
        self.launchd_dir = self.LAUNCHD_DIR
        self.launchd_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path("/Users/twinssn/Projects/aikorea24/logs")
        self.log_dir.mkdir(exist_ok=True)
    
    def generate_plist(self, job: LaunchdJob) -> str:
        """launchd plist XML 생성"""
        plist = {
            "Label": job.label,
            "Program": job.program,
            "ProgramArguments": job.args,
            "WorkingDirectory": job.working_directory,
            "StartCalendarInterval": job.start_calendar,
            "RunAtLoad": job.run_at_load,
            "KeepAlive": job.keep_alive,
            "StandardOutPath": job.standard_out_path,
            "StandardErrorPath": job.standard_error_path,
        }
        
        if job.environment:
            plist["EnvironmentVariables"] = job.environment
        
        return plistlib.dumps(plist, fmt=plistlib.FMT_XML).decode()
    
    def install(self, job_name: str = None) -> bool:
        """launchd 작업 설치"""
        jobs = [self.JOBS[job_name]] if job_name else list(self.JOBS.values())
        
        for job in jobs:
            plist_path = self.launchd_dir / f"{job.label}.plist"
            plist_content = self.generate_plist(job)
            
            # 기존 plist 백업
            if plist_path.exists():
                backup = plist_path.with_suffix(".plist.bak")
                plist_path.rename(backup)
                logger.info(f"백업: {backup}")
            
            plist_path.write_text(plist_content)
            logger.info(f"설치: {plist_path}")
            
            # load
            result = subprocess.run(
                ["launchctl", "load", str(plist_path)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                logger.warning(f"load 실패 (이미 로드됨일 수 있음): {result.stderr}")
            else:
                logger.info(f"✅ launchd 로드: {job.label}")
        
        return True
    
    def uninstall(self, job_name: str = None) -> bool:
        """launchd 작업 제거"""
        jobs = [self.JOBS[job_name]] if job_name else list(self.JOBS.values())
        
        for job in jobs:
            plist_path = self.launchd_dir / f"{job.label}.plist"
            if plist_path.exists():
                # unload
                subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
                plist_path.unlink()
                logger.info(f"제거: {job.label}")
        
        return True
    
    def status(self, job_name: str = None) -> dict:
        """작업 상태 확인"""
        jobs = [self.JOBS[job_name]] if job_name else list(self.JOBS.values())
        results = {}
        
        for job in jobs:
            plist_path = self.launchd_dir / f"{job.label}.plist"
            installed = plist_path.exists()
            
            # launchctl list로 실행 상태 확인
            result = subprocess.run(
                ["launchctl", "list", job.label],
                capture_output=True, text=True
            )
            running = result.returncode == 0 and job.label in result.stdout
            
            results[job.label] = {
                "installed": installed,
                "running": running,
                "plist_path": str(self.launchd_dir / f"{job.label}.plist"),
            }
        
        return results


# ──────────────────────────────────────────────
# Linux systemd 지원 (선택적)
# ──────────────────────────────────────────────

class SystemdScheduler:
    """Linux systemd 스케줄러 (선택적)"""
    
    SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
    
    JOBS = {
        "aikorea24-carousel": {
            "description": "Instagram Carousel 자동 발행 (매일 08:00)",
            "exec": "/usr/bin/python3 -m scripts.threads.v3.auto_poster.main --mode carousel",
            "working_dir": "/Users/twinssn/Projects/aikorea24",
            "schedule": "0 8 * * *",  # 매일 08:00
        },
        "aikorea24-reels": {
            "description": "Instagram Reels 자동 발행 (매일 19:00)",
            "exec": "/usr/bin/python3 -m scripts.threads.v3.auto_poster.main --mode reels",
            "working_dir": "/Users/twinssn/Projects/aikorea24",
            "schedule": "0 19 * * *",  # 매일 19:00
        },
    }
    
    def __init__(self):
        self.systemd_dir = self.SYSTEMD_DIR
        self.systemd_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_service(self, job_name: str) -> str:
        job = self.JOBS[job_name]
        return f"""[Unit]
Description={job['description']}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={job['working_dir']}
ExecStart={job['exec']}
Environment=PYTHONPATH={job['working_dir']}
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
    
    def generate_timer(self, job_name: str) -> str:
        job = self.JOBS[job_name]
        return f"""[Unit]
Description=Timer for {job['description']}
Requires={job_name}.service

[Timer]
OnCalendar={job['schedule']}
Persistent=true

[Install]
WantedBy=timers.target
"""
    
    def install(self, job_name: str = None) -> bool:
        jobs = [job_name] if job_name else list(self.JOBS.keys())
        
        for name in jobs:
            service = self.generate_service(name)
            timer = self.generate_timer(name)
            
            service_path = self.SYSTEMD_DIR / f"{name}.service"
            timer_path = self.SYSTEMD_DIR / f"{name}.timer"
            
            service_path.write_text(service)
            timer_path.write_text(timer)
            
            # systemd reload & enable
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "--user", "enable", f"{name}.timer"], check=True)
            subprocess.run(["systemctl", "--user", "start", f"{name}.timer"], check=True)
            
            print(f"✅ systemd 설치: {name}")
        
        return True


# ──────────────────────────────────────────────
# 공통 인터페이스
# ──────────────────────────────────────────────

def get_scheduler() -> LaunchdScheduler | SystemdScheduler:
    """플랫폼별 스케줄러 반환"""
    import sys
    if sys.platform == "darwin":
        return LaunchdScheduler()
    else:
        return SystemdScheduler()


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    scheduler = get_scheduler()
    
    if len(sys.argv) < 2:
        print("Usage: python scheduler.py [install|uninstall|status] [job_name]")
        sys.exit(1)
    
    action = sys.argv[1]
    job = sys.argv[2] if len(sys.argv) > 2 else None
    
    if action == "install":
        scheduler.install(job)
    elif action == "uninstall":
        scheduler.uninstall(job)
    elif action == "status":
        print(scheduler.status(job))
    else:
        print(f"Unknown action: {action}")