from github_auto.config import Config, Account

def test_config_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    c = Config(path)
    c.add_account("a", Account("user", "u@example.com", "~/.ssh/key", "github-a"))
    c2 = Config(path)
    assert c2.current_account_name() == "a"
    assert c2.get_account("a").username == "user"
