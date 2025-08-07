### Auto Attendance

Customization for Auto Attendance

For Data use this : https://sohcm.com/SmartApp_ess/api/SwipeDetails/GetDeviceLogs?APIKey=233916012427&AccountName=ACE&FromDate=2025-05-15&ToDate=2025-05-15

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app auto_attendance
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/auto_attendance
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
