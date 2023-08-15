class MockRedis:
    def __init__(self, cache=dict()):
        self.cache = cache

    def get(self, key):
        if key in self.cache:
            return self.cache[key]
        return None  # return nil

    def set(self, key, value, *args, **kwargs):
        if self.cache:
            self.cache[key] = value
            return "OK"
        return None  # return nil in case of some issue

    def hget(self, hash, key):
        if hash in self.cache:
            if key in self.cache[hash]:
                return self.cache[hash][key]
        return None  # return nil

    def hset(self, hash, key, value, *args, **kwargs):
        if self.cache:
            self.cache[hash][key] = value
            return 1
        return None  # return nil in case of some issue

    def lpush(self, key, value):
        # Simulate the LPUSH command in Redis
        # print(f"lpush: {key} {value}")
        if key not in self.cache:
            self.cache[key] = []
        self.cache[key].insert(0, value)

    def lpop(self, key):
        # Simulate the LPOP command in Redis
        if (
            key in self.cache
            and isinstance(self.cache[key], list)
            and len(self.cache[key]) > 0
        ):
            # print(f"lpop: {self.cache[key]}")
            return self.cache[key].pop(0)
        else:
            return None

    def exists(self, key):
        if key in self.cache:
            return 1
        return 0

    def cache_overwrite(self, cache=dict()):
        self.cache = cache

    def llen(self, key):
        # Simulate the LLEN command in Redis
        if key in self.cache and isinstance(self.cache[key], list):
            return len(self.cache[key])
        else:
            return 0