# OTA Fault Injection Configuration Examples
# 可复用的故障配置示例，用于快速启动特定场景

# ============================================================================
# 使用方式：
#   在 ota_cli_test.py 或自定义脚本中：
#   
#   from ymodem_fault_injector import FaultConfig
#   from test_scenarios import SCENARIO_CONFIGS
#   
#   config = SCENARIO_CONFIGS['high_latency']
#   ymodem = Ymodem(fault_config=config)
# ============================================================================

SCENARIO_CONFIGS = {
    # 基准测试 - 无任何故障
    'baseline': {
        'name': 'Baseline - No Faults',
        'description': '基准测试，用于对比有故障情况下的性能下降',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.0,
            'ack_delay_ms': 0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    },
    
    # 延迟类故障
    'high_latency': {
        'name': 'High Latency',
        'description': '模拟高延迟网络（500-2000ms）',
        'config': {
            'scenario': 'high_latency',
        }
    },
    
    'very_high_latency': {
        'name': 'Very High Latency',
        'description': '模拟极端延迟网络（2000-5000ms）',
        'config': {
            'scenario': None,
            'ack_delay_ms': 3500,
            'ack_loss_probability': 0.0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    },
    
    # 丢包类故障
    'light_packet_loss': {
        'name': 'Light Packet Loss',
        'description': '轻度丢包（5%）',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.05,
            'ack_delay_ms': 0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    },
    
    'medium_packet_loss': {
        'name': 'Medium Packet Loss',
        'description': '中等丢包（15%） - 真实3G网络典型值',
        'config': {
            'scenario': 'packet_loss',
        }
    },
    
    'heavy_packet_loss': {
        'name': 'Heavy Packet Loss',
        'description': '重型丢包（30%） - 极限条件',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.30,
            'ack_delay_ms': 0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    },
    
    'extreme_packet_loss': {
        'name': 'Extreme Packet Loss',
        'description': '超极限丢包（50%） - 压力测试',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.50,
            'ack_delay_ms': 0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    },
    
    # 实际环境模拟
    'mobile_3g': {
        'name': 'Mobile 3G Network',
        'description': '模拟3G移动网络：5%丢包 + 100-500ms延迟',
        'config': {
            'scenario': 'intermittent',
        }
    },
    
    'poor_wifi': {
        'name': 'Poor WiFi Connection',
        'description': '模拟信号弱WiFi：10%丢包 + 200-1000ms延迟',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.10,
            'ack_delay_ms': 600,
            'duplicate_ack_probability': 0.05,
            'data_corruption_probability': 0.0,
        }
    },
    
    'unstable_connection': {
        'name': 'Unstable Connection',
        'description': '不稳定连接：20%丢包 + 500-2000ms延迟 + 重复',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.20,
            'ack_delay_ms': 1250,
            'duplicate_ack_probability': 0.10,
            'data_corruption_probability': 0.0,
        }
    },
    
    # 特定故障模式
    'duplicate_acks': {
        'name': 'Duplicate ACKs',
        'description': '重复ACK响应（20%） - 测试状态处理',
        'config': {
            'scenario': 'duplicate_acks',
        }
    },
    
    'data_corruption': {
        'name': 'Data Corruption',
        'description': '数据损坏（10%） - 测试CRC',
        'config': {
            'scenario': 'corrupted_data',
        }
    },
    
    # 组合压力测试
    'combined_stress': {
        'name': 'Combined Stress',
        'description': '综合压力：15%丢包 + 1000ms延迟 + 10%重复',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.15,
            'ack_delay_ms': 1000,
            'duplicate_ack_probability': 0.10,
            'data_corruption_probability': 0.0,
        }
    },
    
    'extreme_stress': {
        'name': 'Extreme Stress Test',
        'description': '极限压力：30%丢包 + 2000ms延迟 + 15%重复 + 5%损坏',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.30,
            'ack_delay_ms': 2000,
            'duplicate_ack_probability': 0.15,
            'data_corruption_probability': 0.05,
        }
    },
    
    # 边界条件
    'just_below_timeout': {
        'name': 'Just Below Timeout (29s)',
        'description': '延迟接近超时边界（29秒），测试超时处理',
        'config': {
            'scenario': None,
            'ack_delay_ms': 29000,
            'ack_loss_probability': 0.0,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    },
    
    # 特定场景
    'mqtt_congestion': {
        'name': 'MQTT Broker Congestion',
        'description': '模拟MQTT broker拥塞：10%丢包 + 高变化延迟',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.10,
            'ack_delay_ms': 800,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    },
    
    'receiver_overload': {
        'name': 'Receiver Overload',
        'description': '模拟接收端过载：高延迟 + 偶发丢包',
        'config': {
            'scenario': None,
            'ack_loss_probability': 0.05,
            'ack_delay_ms': 2500,
            'duplicate_ack_probability': 0.0,
            'data_corruption_probability': 0.0,
        }
    },
}


def get_scenario(name: str) -> dict:
    """获取预定义场景配置"""
    if name not in SCENARIO_CONFIGS:
        return None
    return SCENARIO_CONFIGS[name]


def list_scenarios() -> list:
    """列出所有可用场景"""
    return list(SCENARIO_CONFIGS.keys())


def get_scenario_info(name: str) -> tuple:
    """获取场景信息 (display_name, description)"""
    scenario = SCENARIO_CONFIGS.get(name)
    if scenario:
        return scenario['name'], scenario['description']
    return None, None


# 快速参考
QUICK_REFERENCE = {
    'quick_test': ['baseline', 'mobile_3g', 'extreme_stress'],
    'full_regression': ['baseline', 'light_packet_loss', 'medium_packet_loss', 
                        'heavy_packet_loss', 'high_latency', 'poor_wifi', 
                        'duplicate_acks', 'combined_stress'],
    'stress_only': ['medium_packet_loss', 'high_latency', 'combined_stress', 'extreme_stress'],
    'network_conditions': ['mobile_3g', 'poor_wifi', 'unstable_connection'],
}


if __name__ == '__main__':
    print("Available Test Scenarios:")
    print("=" * 70)
    for name, config in SCENARIO_CONFIGS.items():
        print(f"\n{name:30s} | {config['name']}")
        print(f"{'':30s} | {config['description']}")
    
    print("\n" + "=" * 70)
    print("\nQuick Reference:")
    for key, scenarios in QUICK_REFERENCE.items():
        print(f"  {key:25s}: {', '.join(scenarios)}")
