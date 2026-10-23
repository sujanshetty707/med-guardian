.PHONY: install seed test sim run register clean

install:
	pip install -r requirements.txt

seed:
	python scripts/seed_demo_data.py

test:
	pytest -v tests/

sim:
	python tests/e2e_chat_sim.py

register:
	python scripts/register_agents.py

run:
	python scripts/run_agents.py

clean:
	rm -f medguardian.db
