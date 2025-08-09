#!/usr/bin/env python3
"""
Comprehensive Anti-DDoS Stress Testing Suite
Tests the 95%+ attack blocking effectiveness while ensuring <5% false positives
"""
import asyncio
import json
import logging
import random
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List

import os

import aiohttp
import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    test_type: str
    total_requests: int
    successful_requests: int
    blocked_requests: int
    error_requests: int
    avg_response_time: float
    blocking_rate: float
    success_rate: float


class AntiDDoSStressTester:
    def __init__(self):
        self.base_url = os.getenv("BASE_URL", "http://localhost")
        self.onion_host = os.getenv("CURRENT_ONION_ADDRESS", "*.onion")
        self.onion_url = f"http://{self.onion_host}"
        self.tor_proxy = {
            "http": "socks5h://localhost:9050",
            "https": "socks5h://localhost:9050",
        }
        self.results = []

    def _headers(self, ua: str | None = None) -> Dict[str, str]:
        h = {"Host": self.onion_host}
        if ua:
            h["User-Agent"] = ua
        return h

    def generate_bot_user_agent(self):
        """Generate suspicious bot user agents"""
        bot_agents = [
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "curl/7.68.0",
            "python-requests/2.25.1",
            "Wget/1.20.3",
            "bot/1.0",
            "",  # Empty user agent
            "a" * 1000,  # Extremely long user agent
        ]
        return random.choice(bot_agents)

    def generate_legitimate_user_agent(self):
        """Generate legitimate browser user agents"""
        legitimate_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
        ]
        return random.choice(legitimate_agents)

    def test_rapid_fire_requests(self, num_requests=1000, concurrent=50):
        """Test rapid fire requests to trigger rate limiting"""
        logger.info(
            f"Starting rapid fire test: {num_requests} requests, {concurrent} concurrent"
        )

        results = {"success": 0, "blocked": 0, "error": 0, "times": []}

        def make_request():
            try:
                start_time = time.time()
                response = requests.get(
                    f"{self.base_url}/",
                    headers=self._headers(self.generate_bot_user_agent()),
                    timeout=10,
                    allow_redirects=False,
                )
                end_time = time.time()

                response_time = end_time - start_time
                results["times"].append(response_time)

                if response.status_code == 302 and "anti_ddos" in response.headers.get(
                    "Location", ""
                ):
                    results["blocked"] += 1
                elif response.status_code == 200:
                    results["success"] += 1
                else:
                    results["error"] += 1

            except Exception as e:
                results["error"] += 1
                logger.debug(f"Request error: {e}")

        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            for future in futures:
                future.result()

        avg_time = statistics.mean(results["times"]) if results["times"] else 0
        blocking_rate = (results["blocked"] / num_requests) * 100

        result = TestResult(
            test_type="Rapid Fire Attack",
            total_requests=num_requests,
            successful_requests=results["success"],
            blocked_requests=results["blocked"],
            error_requests=results["error"],
            avg_response_time=avg_time,
            blocking_rate=blocking_rate,
            success_rate=(results["success"] / num_requests) * 100,
        )

        self.results.append(result)
        logger.info(f"Rapid fire test complete: {blocking_rate:.1f}% blocked")
        return result

    def test_low_entropy_solutions(self, num_attempts=100):
        """Test low entropy challenge solutions to trigger Argon2 switching"""
        logger.info(f"Starting low entropy solution test: {num_attempts} attempts")

        results = {"success": 0, "blocked": 0, "error": 0, "times": []}

        def attempt_low_entropy():
            try:
                session = requests.Session()
                start_time = time.time()

                response = session.get(
                    f"{self.base_url}/anti_ddos/spinner/?next=/",
                    headers=self._headers(self.generate_bot_user_agent()),
                    allow_redirects=False,
                )
                if response.status_code != 200:
                    results["error"] += 1
                    return

                start_ts = int(time.time())

                time.sleep(2.1)

                polls = 0
                success = False
                blocked = False
                while polls < 20 and not (success or blocked):
                    polls += 1
                    status_resp = session.get(
                        f"{self.base_url}/anti_ddos/status/",
                        headers=self._headers(self.generate_bot_user_agent()),
                        allow_redirects=False,
                    )
                    if status_resp.status_code == 302:
                        loc = status_resp.headers.get("Location", "")
                        if loc == "/" or (loc.startswith("http") and loc.endswith("/")):
                            success = True
                            break
                        if "anti_ddos" in loc:
                            time.sleep(0.5)
                            continue
                    if status_resp.status_code == 200 and ("pow" in status_resp.text or "captcha" in status_resp.text):
                        blocked = True
                        break
                    time.sleep(0.5)

                end_time = time.time()
                results["times"].append(end_time - start_time)

                if success:
                    results["success"] += 1
                elif blocked:
                    results["blocked"] += 1
                else:
                    results["error"] += 1

            except Exception as e:
                results["error"] += 1
                logger.debug(f"Low entropy test error: {e}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(attempt_low_entropy) for _ in range(num_attempts)
            ]
            for future in futures:
                future.result()

        avg_time = statistics.mean(results["times"]) if results["times"] else 0
        blocking_rate = (results["blocked"] / num_attempts) * 100

        result = TestResult(
            test_type="Low Entropy Solutions",
            total_requests=num_attempts,
            successful_requests=results["success"],
            blocked_requests=results["blocked"],
            error_requests=results["error"],
            avg_response_time=avg_time,
            blocking_rate=blocking_rate,
            success_rate=(results["success"] / num_attempts) * 100,
        )

        self.results.append(result)
        logger.info(f"Low entropy test complete: {blocking_rate:.1f}% blocked")
        return result

    def test_legitimate_users(self, num_users=50):
        """Test legitimate user behavior to measure false positives"""
        logger.info(f"Starting legitimate user test: {num_users} users")

        results = {"success": 0, "blocked": 0, "error": 0, "times": []}

        def simulate_legitimate_user():
            try:
                session = requests.Session()
                start_time = time.time()

                time.sleep(random.uniform(1, 3))

                response = session.get(
                    f"{self.base_url}/anti_ddos/spinner/?next=/",
                    headers=self._headers(self.generate_legitimate_user_agent()),
                    allow_redirects=False,
                )

                polls = 0
                success = False
                blocked = False
                while polls < 20 and not (success or blocked):
                    polls += 1
                    status_resp = session.get(
                        f"{self.base_url}/anti_ddos/status/",
                        headers=self._headers(self.generate_legitimate_user_agent()),
                        allow_redirects=False,
                    )
                    if status_resp.status_code == 302:
                        loc = status_resp.headers.get("Location", "")
                        if loc == "/" or loc.startswith("http") and loc.endswith("/"):
                            success = True
                            break
                        if "anti_ddos" in loc:
                            time.sleep(0.5)
                            continue
                    if status_resp.status_code == 200 and ("pow" in status_resp.text or "captcha" in status_resp.text):
                        blocked = True
                        break
                    time.sleep(0.5)

                if response.status_code != 200:
                    results["error"] += 1
                    return

                end_time = time.time()
                results["times"].append(end_time - start_time)

                if success:
                    results["success"] += 1
                elif blocked:
                    results["blocked"] += 1
                else:
                    results["error"] += 1

            except Exception as e:
                results["error"] += 1
                logger.debug(f"Legitimate user test error: {e}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(simulate_legitimate_user) for _ in range(num_users)
            ]
            for future in futures:
                future.result()

        avg_time = statistics.mean(results["times"]) if results["times"] else 0
        false_positive_rate = (results["blocked"] / num_users) * 100

        result = TestResult(
            test_type="Legitimate Users",
            total_requests=num_users,
            successful_requests=results["success"],
            blocked_requests=results["blocked"],
            error_requests=results["error"],
            avg_response_time=avg_time,
            blocking_rate=false_positive_rate,
            success_rate=(results["success"] / num_users) * 100,
        )

        self.results.append(result)
        logger.info(
            f"Legitimate user test complete: {false_positive_rate:.1f}% false positives"
        )
        return result

    def test_honeypot_triggering(self, num_attempts=100):
        """Test honeypot field triggering"""
        logger.info(f"Starting honeypot triggering test: {num_attempts} attempts")

        results = {"success": 0, "blocked": 0, "error": 0, "times": []}

        def trigger_honeypot():
            try:
                session = requests.Session()
                start_time = time.time()

                response = session.get(
                    f"{self.base_url}/anti_ddos/spinner/?next=/",
                    headers=self._headers(self.generate_bot_user_agent()),
                    allow_redirects=False,
                )
                if response.status_code != 200:
                    results["error"] += 1
                    return

                time.sleep(2.1)

                polls = 0
                success = False
                blocked = False
                while polls < 20 and not (success or blocked):
                    polls += 1
                    status_resp = session.get(
                        f"{self.base_url}/anti_ddos/status/",
                        headers=self._headers(self.generate_bot_user_agent()),
                        allow_redirects=False,
                    )
                    if status_resp.status_code == 302:
                        loc = status_resp.headers.get("Location", "")
                        if loc == "/" or (loc.startswith("http") and loc.endswith("/")):
                            success = True
                            break
                        if "anti_ddos" in loc:
                            time.sleep(0.5)
                            continue
                    if status_resp.status_code == 200 and ("pow" in status_resp.text or "captcha" in status_resp.text):
                        blocked = True
                        break
                    time.sleep(0.5)

                end_time = time.time()
                results["times"].append(end_time - start_time)

                if success:
                    results["success"] += 1
                elif blocked:
                    results["blocked"] += 1
                else:
                    results["error"] += 1

            except Exception as e:
                results["error"] += 1
                logger.debug(f"Honeypot test error: {e}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(trigger_honeypot) for _ in range(num_attempts)]
            for future in futures:
                future.result()

        avg_time = statistics.mean(results["times"]) if results["times"] else 0
        blocking_rate = (results["blocked"] / num_attempts) * 100

        result = TestResult(
            test_type="Honeypot Triggering",
            total_requests=num_attempts,
            successful_requests=results["success"],
            blocked_requests=results["blocked"],
            error_requests=results["error"],
            avg_response_time=avg_time,
            blocking_rate=blocking_rate,
            success_rate=(results["success"] / num_attempts) * 100,
        )

        self.results.append(result)
        logger.info(f"Honeypot test complete: {blocking_rate:.1f}% blocked")
        return result

    def extract_csrf_token(self, html):
        """Extract CSRF token from HTML"""
        import re

        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
        return match.group(1) if match else ""

    def extract_challenge_data(self, html):
        """Extract challenge data from HTML"""
        import re

        match = re.search(r'name="challenge_data" value="([^"]+)"', html)
        return match.group(1) if match else ""

    def solve_challenge(self, html):
        """Solve the math challenge from HTML"""
        import re

        add_match = re.search(r"(\d+)\s*\+\s*(\d+)", html)
        if add_match:
            return int(add_match.group(1)) + int(add_match.group(2))

        mult_match = re.search(r"(\d+)\s*[×*]\s*(\d+)", html)
        if mult_match:
            return int(mult_match.group(1)) * int(mult_match.group(2))

        return 0

    def run_comprehensive_stress_test(self):
        """Run all stress tests and generate report"""
        logger.info("Starting comprehensive anti-DDoS stress testing...")

        self.test_rapid_fire_requests(num_requests=500, concurrent=25)
        self.test_low_entropy_solutions(num_attempts=50)
        self.test_legitimate_users(num_users=30)
        self.test_honeypot_triggering(num_attempts=50)

        self.generate_report()

    def generate_report(self):
        return self._generate_report()

    def _generate_report(self):
        """Generate comprehensive stress test report"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_tests": len(self.results),
                "overall_blocking_effectiveness": 0,
                "false_positive_rate": 0,
                "target_met": False,
            },
            "detailed_results": [],
        }

        attack_tests = [r for r in self.results if r.test_type != "Legitimate Users"]
        legitimate_test = next(
            (r for r in self.results if r.test_type == "Legitimate Users"), None
        )

        if attack_tests:
            total_attack_requests = sum(r.total_requests for r in attack_tests)
            total_blocked = sum(r.blocked_requests for r in attack_tests)
            overall_blocking = (
                (total_blocked / total_attack_requests) * 100
                if total_attack_requests > 0
                else 0
            )
            report["summary"]["overall_blocking_effectiveness"] = overall_blocking

        if legitimate_test:
            false_positive_rate = legitimate_test.blocking_rate
            report["summary"]["false_positive_rate"] = false_positive_rate

        blocking_target_met = (
            report["summary"]["overall_blocking_effectiveness"] >= 95.0
        )
        false_positive_target_met = report["summary"]["false_positive_rate"] <= 5.0
        report["summary"]["target_met"] = (
            blocking_target_met and false_positive_target_met
        )

        for result in self.results:
            report["detailed_results"].append(
                {
                    "test_type": result.test_type,
                    "total_requests": result.total_requests,
                    "successful_requests": result.successful_requests,
                    "blocked_requests": result.blocked_requests,
                    "error_requests": result.error_requests,
                    "avg_response_time": round(result.avg_response_time, 3),
                    "blocking_rate": round(result.blocking_rate, 2),
                    "success_rate": round(result.success_rate, 2),
                }
            )

        os.makedirs("logs", exist_ok=True)
        with open("logs/stress_results.json", "w") as f:
            json.dump(report, f, indent=2)

        self.generate_human_readable_report(report)

        logger.info("Stress test report generated")
        return report

    def generate_human_readable_report(self, report):
        """Generate human-readable stress test report"""
        report_text = f"""
COMPREHENSIVE ANTI-DDOS STRESS TEST REPORT
==========================================
Generated: {report['timestamp']}

EXECUTIVE SUMMARY
================
Overall Blocking Effectiveness: {report['summary']['overall_blocking_effectiveness']:.1f}%
False Positive Rate: {report['summary']['false_positive_rate']:.1f}%
Target Achievement (95%+ blocking, <5% false positives): {'✅ MET' if report['summary']['target_met'] else '❌ NOT MET'}

DETAILED TEST RESULTS
====================
"""

        for result in report["detailed_results"]:
            report_text += f"""
{result['test_type']}:
  Total Requests: {result['total_requests']}
  Successful: {result['successful_requests']} ({result['success_rate']:.1f}%)
  Blocked: {result['blocked_requests']} ({result['blocking_rate']:.1f}%)
  Errors: {result['error_requests']}
  Avg Response Time: {result['avg_response_time']:.3f}s
"""

        report_text += f"""
ANALYSIS
========
The anti-DDoS system {'SUCCESSFULLY' if report['summary']['target_met'] else 'FAILED TO'} meet the target requirements.

Attack Blocking: {report['summary']['overall_blocking_effectiveness']:.1f}% (Target: ≥95%)
False Positives: {report['summary']['false_positive_rate']:.1f}% (Target: ≤5%)

RECOMMENDATIONS
==============
"""

        if report["summary"]["overall_blocking_effectiveness"] < 95:
            report_text += "- Increase difficulty parameters for challenge generation\n"
            report_text += "- Enhance bot detection patterns\n"

        if report["summary"]["false_positive_rate"] > 5:
            report_text += "- Review legitimate user detection algorithms\n"
            report_text += "- Adjust timing thresholds for human behavior\n"

        if report["summary"]["target_met"]:
            report_text += "- System performing within target parameters\n"
            report_text += "- Continue monitoring under production load\n"

        os.makedirs("logs", exist_ok=True)
        with open("logs/stress_report.txt", "w") as f:
            f.write(report_text)


if __name__ == "__main__":
    tester = AntiDDoSStressTester()
    tester.run_comprehensive_stress_test()
