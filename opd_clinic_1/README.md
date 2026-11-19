### ood_clinic_1

ood

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/nareshvjn/opd_clinic_1 --branch develop
bench --site $NAME_OF_YOUR_SITE install-app opd_clinic_1
bench --site $NAME_OF_YOUR_SITE migrate
bench --site $NAME_OF_YOUR_SITE clear-cache
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/opd_clinic_1
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
