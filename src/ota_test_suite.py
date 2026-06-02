"""
OTA Test Suite Runner
用于自动化运行多个故障场景的测试套件
"""
import os
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


class TestScenario:
    """单个测试场景定义"""
    
    def __init__(self, name: str, description: str, config: dict):
        self.name = name
        self.description = description
        self.config = config  # FaultConfig as dict
        
    def __repr__(self):
        return f"Scenario({self.name})"


# 预定义的测试场景
TEST_SCENARIOS = [
    TestScenario(
        name="Scenario 1: No Faults",
        description="基准测试 - 无任何故障",
        config={
            'scenario': None,
            'ack_loss_probability': 0.0,
            'ack_delay_ms': 0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    ),
    TestScenario(
        name="Scenario 2: High Latency",
        description="高延迟测试 - 500-2000ms ACK延迟",
        config={
            'scenario': 'high_latency',
        }
    ),
    TestScenario(
        name="Scenario 3: Light Packet Loss",
        description="轻度丢包测试 - 5% ACK丢包率",
        config={
            'scenario': None,
            'ack_loss_probability': 0.05,
            'ack_delay_ms': 0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    ),
    TestScenario(
        name="Scenario 4: Medium Packet Loss",
        description="中等丢包测试 - 15% ACK丢包率",
        config={
            'scenario': 'packet_loss',
        }
    ),
    TestScenario(
        name="Scenario 5: Heavy Packet Loss",
        description="重型丢包测试 - 30% ACK丢包率",
        config={
            'scenario': None,
            'ack_loss_probability': 0.30,
            'ack_delay_ms': 0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    ),
    TestScenario(
        name="Scenario 6: Intermittent Issues",
        description="间歇性问题 - 结合延迟和丢包",
        config={
            'scenario': 'intermittent',
        }
    ),
    TestScenario(
        name="Scenario 7: Duplicate ACKs",
        description="重复ACK测试 - 20% ACK会发送两次",
        config={
            'scenario': 'duplicate_acks',
        }
    ),
    TestScenario(
        name="Scenario 8: Combined Stress",
        description="综合压力测试 - 高延迟+丢包+重复ACK",
        config={
            'scenario': None,
            'ack_loss_probability': 0.15,
            'ack_delay_ms': 1000,
            'duplicate_ack_probability': 0.1,
            'data_corruption_probability': 0.0,
        }
    ),
    TestScenario(
        name="Scenario 9: Extreme Conditions",
        description="极限条件测试 - 所有故障都启用",
        config={
            'scenario': None,
            'ack_loss_probability': 0.30,
            'ack_delay_ms': 2000,
            'duplicate_ack_probability': 0.15,
            'data_corruption_probability': 0.05,
        }
    ),
]


class TestReport:
    """测试报告"""
    
    def __init__(self):
        self.results = []
        self.timestamp = datetime.now()
        
    def add_result(self, scenario_name: str, success: bool, elapsed_time: float, 
                   stats: dict, error_msg: str = None):
        """添加单个测试结果"""
        self.results.append({
            'scenario': scenario_name,
            'success': success,
            'elapsed_time': elapsed_time,
            'stats': stats,
            'error': error_msg,
            'timestamp': datetime.now().isoformat(),
        })
        
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "="*80)
        print(f"TEST REPORT - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        passed = sum(1 for r in self.results if r['success'])
        total = len(self.results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ✓")
        print(f"Failed: {total - passed} ✗")
        print(f"Success Rate: {100*passed/total:.1f}%\n")
        
        for result in self.results:
            status = "✓ PASS" if result['success'] else "✗ FAIL"
            print(f"{status} | {result['scenario']}")
            print(f"      Time: {result['elapsed_time']:.1f}s")
            if result['stats']:
                print(f"      Retries: {result['stats'].get('total_retries', 'N/A')}")
                print(f"      ACKs dropped: {result['stats'].get('acks_dropped', 'N/A')}")
            if result['error']:
                print(f"      Error: {result['error']}")
            print()
        
        print("="*80)
        
    def save_json(self, filepath: str):
        """保存为JSON报告"""
        with open(filepath, 'w') as f:
            json.dump({
                'timestamp': self.timestamp.isoformat(),
                'results': self.results,
            }, f, indent=2)
        print(f"Report saved: {filepath}")


def create_auto_config(scenario: TestScenario) -> str:
    """
    为场景创建自动配置脚本
    返回EOF分隔的输入字符串
    """
    inputs = []
    
    # MQTT配置（使用默认值）
    inputs.append("")  # broker
    inputs.append("")  # port
    inputs.append("")  # username
    inputs.append("")  # password
    
    # OTA主题（使用默认值）
    inputs.append("")  # topic
    
    # 故障场景选择
    if scenario.config.get('scenario'):
        # 如果是预设场景
        scenario_map = {
            'high_latency': '1',
            'packet_loss': '2',
            'intermittent': '3',
            'corrupted_data': '4',
            'duplicate_acks': '5',
        }
        inputs.append(scenario_map.get(scenario.config['scenario'], '0'))
    else:
        # 手动配置
        inputs.append('0')
        inputs.append(str(scenario.config.get('ack_loss_probability', 0.0)))
        inputs.append(str(scenario.config.get('ack_delay_ms', 0)))
        inputs.append(str(scenario.config.get('duplicate_ack_probability', 0.0)))
        inputs.append(str(scenario.config.get('data_corruption_probability', 0.0)))
    
    # 是否等待C
    inputs.append("")  # default Y
    
    return "\n".join(inputs) + "\n"


def run_scenario(scenario: TestScenario, firmware_path: str, script_path: str, 
                timeout: int = 300) -> tuple:
    """
    运行单个测试场景
    返回 (success, elapsed_time, stats_dict, error_message)
    """
    print(f"\n{'='*80}")
    print(f"Running: {scenario.name}")
    print(f"Description: {scenario.description}")
    print(f"{'='*80}")
    
    config_input = create_auto_config(scenario)
    
    try:
        start_time = time.time()
        
        # 运行测试脚本
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=os.path.dirname(script_path),
            text=True,
        )
        
        try:
            stdout, _ = process.communicate(input=config_input, timeout=timeout)
            elapsed = time.time() - start_time
            
            # 检查成功标志
            success = "completed successfully" in stdout.lower()
            
            # 解析统计信息
            stats = {}
            for line in stdout.split('\n'):
                if 'total_retries:' in line:
                    try:
                        stats['total_retries'] = int(line.split(':')[1].strip())
                    except:
                        pass
                elif 'acks_dropped:' in line:
                    try:
                        stats['acks_dropped'] = int(line.split(':')[1].strip())
                    except:
                        pass
            
            # 打印输出
            print("\n--- Output ---")
            print(stdout)
            print("--- End Output ---\n")
            
            return success, elapsed, stats, None
            
        except subprocess.TimeoutExpired:
            process.kill()
            elapsed = time.time() - start_time
            return False, elapsed, {}, f"Timeout after {timeout}s"
            
    except Exception as e:
        return False, 0, {}, str(e)


def main():
    print("OTA Fault Injection Test Suite")
    print("="*80)
    
    # 确保在正确的目录
    if not os.path.exists('src/ota_cli_test.py'):
        print("Error: ota_cli_test.py not found. Please run from project root.")
        sys.exit(1)
    
    if not os.path.exists('scripts/publish_firmware.py'):
        print("Warning: No firmware found. Will use dummy firmware path.")
        firmware_path = "test_firmware.bin"
    else:
        firmware_path = "scripts/publish_firmware.py"
    
    script_path = os.path.abspath('src/ota_cli_test.py')
    
    print(f"\nScript: {script_path}")
    print(f"Firmware: {firmware_path}")
    
    # 显示可用的场景
    print("\nAvailable Test Scenarios:")
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"  {i}. {scenario.name}")
        print(f"     {scenario.description}")
    
    # 让用户选择要运行的场景
    print("\nOptions:")
    print("  'all'  - Run all scenarios")
    print("  '1-5'  - Run scenarios 1 through 5")
    print("  '2,4,6' - Run specific scenarios")
    print("  'quit' - Exit")
    
    choice = input("\nSelect scenarios to run: ").strip().lower()
    
    if choice == 'quit':
        sys.exit(0)
    
    # 解析选择
    selected_scenarios = []
    if choice == 'all':
        selected_scenarios = TEST_SCENARIOS
    else:
        try:
            # 支持范围 (1-5) 和列表 (1,3,5) 格式
            if '-' in choice:
                start, end = map(int, choice.split('-'))
                selected_scenarios = TEST_SCENARIOS[start-1:end]
            else:
                indices = [int(x.strip()) - 1 for x in choice.split(',')]
                selected_scenarios = [TEST_SCENARIOS[i] for i in indices if 0 <= i < len(TEST_SCENARIOS)]
        except:
            print("Invalid selection format")
            sys.exit(1)
    
    if not selected_scenarios:
        print("No scenarios selected")
        sys.exit(1)
    
    # 创建报告
    report = TestReport()
    
    # 运行选定的场景
    for scenario in selected_scenarios:
        success, elapsed, stats, error = run_scenario(
            scenario, 
            firmware_path, 
            script_path,
            timeout=300
        )
        report.add_result(scenario.name, success, elapsed, stats, error)
        
        # 场景之间等待
        if scenario != selected_scenarios[-1]:
            print("\nWaiting 5 seconds before next scenario...")
            time.sleep(5)
    
    # 显示报告
    report.print_summary()
    
    # 保存报告
    report_dir = Path('test_reports')
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report.save_json(str(report_file))


if __name__ == "__main__":
    main()
