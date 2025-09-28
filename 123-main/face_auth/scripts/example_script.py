# a safe example script that can be run from the dashboard
print("Hello from example_script.py")
print("Time:", __import__('datetime').datetime.utcnow().isoformat())
        