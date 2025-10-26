import pytest

try:
    from airflow.models import DagBag
except ImportError:  # pragma: no cover - optional dependency
    DagBag = None


@pytest.mark.skipif(DagBag is None, reason="Airflow not installed")
def test_telegram_collection_dag_loads() -> None:
    dag_bag = DagBag(dag_folder="code/dags", include_examples=False)
    assert "telegram_collection" in dag_bag.dags
    dag = dag_bag.get_dag("telegram_collection")
    assert len(dag.tasks) >= 6
