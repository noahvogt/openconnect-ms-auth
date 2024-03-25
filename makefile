pre-commit-install:
	pre-commit install;
	pre-commit install --hook-type commit-msg;

update-template:
	copier update --trust

cspell-filenames:
	git ls-files | cspell stdin --show-context --locale en-GB,de-CH
