# tests/unit/test_database.py
"""Database 基类单元测试 - sqlite3 wrapper

覆盖:
- Database.query 返回查询结果
- Database.execute 执行单条 SQL 并持久化
- Database.executemany 批量插入
- Database.execute_scripts 执行多语句脚本
"""
import os
import pytest


@pytest.fixture
def db_instance(tmp_path):
    """创建一个测试用 Database 实例,db 文件位于 tmp_path"""
    from util.common.database import Database

    db = Database()
    db.path = str(tmp_path / "test.db")
    return db


def test_database_query_returns_rows(db_instance):
    """query 返回查询结果列表"""
    db_instance.execute(
        "CREATE TABLE IF NOT EXISTS t (id INTEGER, name TEXT)"
    )
    db_instance.execute(
        "INSERT INTO t (id, name) VALUES (?, ?)", (1, "alice")
    )

    rows = db_instance.query("SELECT id, name FROM t WHERE id = ?", (1,))
    assert rows == [(1, "alice")]


def test_database_query_empty_table(db_instance):
    """query 在空表上返回 []"""
    db_instance.execute("CREATE TABLE t (id INTEGER)")
    rows = db_instance.query("SELECT * FROM t")
    assert rows == []


def test_database_execute_persists_across_connections(db_instance):
    """execute 后数据持久化到磁盘,新连接可读到"""
    db_instance.execute("CREATE TABLE t (id INTEGER)")
    db_instance.execute("INSERT INTO t (id) VALUES (100)")

    # 新建一个 Database 实例指向同一文件
    from util.common.database import Database
    other = Database()
    other.path = db_instance.path
    rows = other.query("SELECT * FROM t")
    assert rows == [(100,)]


def test_database_executemany_batch_insert(db_instance):
    """executemany 一次性插入多行"""
    db_instance.execute("CREATE TABLE t (id INTEGER, name TEXT)")
    rows = [(i, f"name_{i}") for i in range(5)]
    db_instance.executemany("INSERT INTO t (id, name) VALUES (?, ?)", rows)

    fetched = db_instance.query("SELECT * FROM t ORDER BY id")
    assert fetched == rows


def test_database_execute_script_multiple_statements(db_instance):
    """execute_script 一次执行多条 SQL(分号分隔)"""
    script = """
    CREATE TABLE t1 (id INTEGER);
    CREATE TABLE t2 (id INTEGER);
    INSERT INTO t1 VALUES (1);
    INSERT INTO t2 VALUES (2);
    """
    db_instance.execute_script(script)

    assert db_instance.query("SELECT * FROM t1") == [(1,)]
    assert db_instance.query("SELECT * FROM t2") == [(2,)]


def test_database_query_with_empty_params(db_instance):
    """query 默认 params=() 时也能工作"""
    db_instance.execute("CREATE TABLE t (id INTEGER)")
    db_instance.execute("INSERT INTO t VALUES (42)")
    rows = db_instance.query("SELECT * FROM t")
    assert rows == [(42,)]


def test_database_execute_with_params_default(db_instance):
    """execute 默认 params=() 时也能工作"""
    db_instance.execute("CREATE TABLE t (id INTEGER)")
    db_instance.execute("INSERT INTO t VALUES (1)")
    # params 默认为 ()
    rows = db_instance.query("SELECT COUNT(*) FROM t")
    assert rows == [(1,)]


def test_database_init_default_path():
    """Database() 默认 path 为空字符串"""
    from util.common.database import Database

    db = Database()
    assert db.path == ""
