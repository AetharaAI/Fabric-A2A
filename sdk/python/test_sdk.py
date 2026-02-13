from fabric_a2a import FabricClient

client = FabricClient(
    base_url="http://localhost:8000",
    token="test-token"
)

print("Client created successfully")
print(client)
