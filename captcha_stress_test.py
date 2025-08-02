#!/usr/bin/env python3
"""
Comprehensive Captcha Stress Test for Anti-DDoS System
Tests captcha functionality under various load conditions and attack patterns
"""

import asyncio
import aiohttp
import time
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CaptchaTestResult:
    test_type: str
    total_attempts: int
    successful_solves: int
    failed_solves: int
    timeouts: int
    avg_solve_time: float
    success_rate: float

class CaptchaStressTester:
    def __init__(self):
        self.base_url = "http://localhost"
        self.results = []
        
    async def fetch_challenge(self, session):
        """Fetch a new challenge from the anti-DDoS system"""
        try:
            async with session.get(f"{self.base_url}/anti_ddos/challenge/", timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    challenge_match = re.search(r'name="challenge_data" value="([^"]+)"', html)
                    start_time_match = re.search(r'name="start_time" value="([^"]+)"', html)
                    
                    if challenge_match and start_time_match:
                        return {
                            'challenge_data': challenge_match.group(1),
                            'start_time': start_time_match.group(1),
                            'html': html
                        }
                return None
        except Exception as e:
            logger.error(f"Error fetching challenge: {e}")
            return None
    
    def solve_math_challenge(self, challenge_data):
        """Solve the mathematical challenge from challenge data"""
        try:
            import base64
            import json
            decoded_data = json.loads(base64.b64decode(challenge_data).decode())
            
            a = decoded_data['a']
            b = decoded_data['b']
            operation = decoded_data.get('operation', '+')
            
            if operation == '+':
                result = a + b
                logger.debug(f"Solved addition: {a} + {b} = {result}")
            else:  # multiplication
                result = a * b
                logger.debug(f"Solved multiplication: {a} × {b} = {result}")
            
            return str(result)
            
        except Exception as e:
            logger.error(f"Failed to solve challenge from data: {e}")
            return "42"  # Fallback
    
    async def submit_solution(self, session, challenge_data, start_time, answer):
        """Submit a solution to the challenge"""
        try:
            data = {
                'challenge_data': challenge_data,
                'start_time': start_time,
                'answer': answer,
                'hp0': '', 'hp1': '', 'hp2': '', 'hp3': '', 'hp4': ''
            }
            
            async with session.post(f"{self.base_url}/anti_ddos/verify/", 
                                  data=data, timeout=10) as response:
                return response.status, await response.text()
        except Exception as e:
            logger.error(f"Error submitting solution: {e}")
            return 0, str(e)
    
    async def legitimate_captcha_solve(self, session):
        """Simulate a legitimate user solving a captcha"""
        start_time = time.time()
        
        challenge = await self.fetch_challenge(session)
        if not challenge:
            return False, time.time() - start_time
        
        answer = self.solve_math_challenge(challenge['challenge_data'])
        
        await asyncio.sleep(1 + (time.time() % 4))
        
        status, response = await self.submit_solution(
            session, challenge['challenge_data'], 
            challenge['start_time'], answer
        )
        
        solve_time = time.time() - start_time
        success = status in [200, 302]  # Success or redirect
        
        return success, solve_time
    
    async def rapid_captcha_solve(self, session):
        """Simulate rapid automated captcha solving (bot behavior)"""
        start_time = time.time()
        
        challenge = await self.fetch_challenge(session)
        if not challenge:
            return False, time.time() - start_time
        
        answer = self.solve_math_challenge(challenge['challenge_data'])
        
        status, response = await self.submit_solution(
            session, challenge['challenge_data'], 
            challenge['start_time'], answer
        )
        
        solve_time = time.time() - start_time
        success = status in [200, 302]
        
        return success, solve_time
    
    async def wrong_answer_test(self, session):
        """Test with intentionally wrong answers"""
        start_time = time.time()
        
        challenge = await self.fetch_challenge(session)
        if not challenge:
            return False, time.time() - start_time
        
        status, response = await self.submit_solution(
            session, challenge['challenge_data'], 
            challenge['start_time'], "wrong_answer"
        )
        
        solve_time = time.time() - start_time
        success = status not in [200, 302]
        
        return success, solve_time
    
    async def run_test_batch(self, test_func, batch_size, test_name):
        """Run a batch of tests concurrently"""
        logger.info(f"Starting {test_name}: {batch_size} attempts")
        
        start_time = time.time()
        successful = 0
        failed = 0
        timeouts = 0
        solve_times = []
        
        async with aiohttp.ClientSession() as session:
            tasks = [test_func(session) for _ in range(batch_size)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    timeouts += 1
                else:
                    success, solve_time = result
                    if success:
                        successful += 1
                    else:
                        failed += 1
                    solve_times.append(solve_time)
        
        avg_solve_time = sum(solve_times) / len(solve_times) if solve_times else 0
        success_rate = (successful / batch_size) * 100
        
        result = CaptchaTestResult(
            test_type=test_name,
            total_attempts=batch_size,
            successful_solves=successful,
            failed_solves=failed,
            timeouts=timeouts,
            avg_solve_time=avg_solve_time,
            success_rate=success_rate
        )
        
        self.results.append(result)
        logger.info(f"{test_name} complete: {success_rate:.1f}% success rate")
        return result
    
    async def run_comprehensive_tests(self):
        """Run all captcha stress tests"""
        logger.info("Starting comprehensive captcha stress testing...")
        
        await self.run_test_batch(
            self.legitimate_captcha_solve, 50, "Legitimate Users"
        )
        
        await self.run_test_batch(
            self.rapid_captcha_solve, 100, "Rapid Bot Solving"
        )
        
        await self.run_test_batch(
            self.wrong_answer_test, 30, "Wrong Answers"
        )
        
        await self.run_test_batch(
            self.legitimate_captcha_solve, 200, "High Concurrency Legitimate"
        )
        
        logger.info("Captcha stress testing complete")
    
    def generate_report(self):
        """Generate comprehensive test report"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_tests": len(self.results),
                "overall_success_rate": sum(r.success_rate for r in self.results) / len(self.results) if self.results else 0,
                "avg_solve_time": sum(r.avg_solve_time for r in self.results) / len(self.results) if self.results else 0
            },
            "detailed_results": [
                {
                    "test_type": r.test_type,
                    "total_attempts": r.total_attempts,
                    "successful_solves": r.successful_solves,
                    "failed_solves": r.failed_solves,
                    "timeouts": r.timeouts,
                    "avg_solve_time": round(r.avg_solve_time, 3),
                    "success_rate": round(r.success_rate, 1)
                }
                for r in self.results
            ]
        }
        
        with open("CAPTCHA_STRESS_TEST_REPORT.json", "w") as f:
            json.dump(report, f, indent=2)
        
        text_report = f"""
COMPREHENSIVE CAPTCHA STRESS TEST REPORT
========================================
Generated: {report['timestamp']}

EXECUTIVE SUMMARY
================
Overall Success Rate: {report['summary']['overall_success_rate']:.1f}%
Average Solve Time: {report['summary']['avg_solve_time']:.3f}s
Total Test Categories: {report['summary']['total_tests']}

DETAILED TEST RESULTS
====================

"""
        
        for result in self.results:
            text_report += f"""
{result.test_type}:
  Total Attempts: {result.total_attempts}
  Successful: {result.successful_solves} ({result.success_rate:.1f}%)
  Failed: {result.failed_solves}
  Timeouts: {result.timeouts}
  Avg Solve Time: {result.avg_solve_time:.3f}s

"""
        
        legitimate_success = next((r.success_rate for r in self.results if "Legitimate" in r.test_type), 0)
        bot_success = next((r.success_rate for r in self.results if "Rapid Bot" in r.test_type), 0)
        
        text_report += f"""
ANALYSIS
========
Legitimate User Success Rate: {legitimate_success:.1f}%
Bot Detection Effectiveness: {100 - bot_success:.1f}%

RECOMMENDATIONS
==============
"""
        
        if legitimate_success < 90:
            text_report += "- Improve legitimate user experience\n"
        if bot_success > 10:
            text_report += "- Enhance bot detection mechanisms\n"
        if legitimate_success >= 90 and bot_success <= 10:
            text_report += "- Captcha system performing well\n"
        
        with open("CAPTCHA_STRESS_TEST_REPORT.txt", "w") as f:
            f.write(text_report)
        
        logger.info("Captcha stress test reports generated")
        return report

async def main():
    tester = CaptchaStressTester()
    await tester.run_comprehensive_tests()
    report = tester.generate_report()
    
    print(f"\nCaptcha Stress Test Summary:")
    print(f"Overall Success Rate: {report['summary']['overall_success_rate']:.1f}%")
    print(f"Average Solve Time: {report['summary']['avg_solve_time']:.3f}s")
    print(f"Reports saved to CAPTCHA_STRESS_TEST_REPORT.txt and .json")

if __name__ == "__main__":
    asyncio.run(main())
