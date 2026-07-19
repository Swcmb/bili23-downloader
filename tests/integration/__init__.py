# tests/integration/__init__.py
"""集成测试包 - 验证解析→下载、登录等完整流程

集成测试不依赖网络/文件系统/数据库真实环境,通过 monkeypatch 与
MagicMock 模拟外部依赖,验证模块间协作的正确性。
"""
