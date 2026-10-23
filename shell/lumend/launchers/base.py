"""Shared shape of a game launcher integration."""


class Launcher:
    id = ""
    name = ""
    # How the user signs in: "steam" (Steam's own window) or "code" (open a
    # web page, sign in, paste the code it shows back into Lumen).
    login = {}

    def available(self):
        return True

    def status(self):
        return {"connected": False, "user": None}

    def describe(self):
        return {"id": self.id, "name": self.name, "available": self.available(),
                "login": self.login, **self.status()}

    def connect(self, payload):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def games(self):
        return []

    def install(self, game_id):
        raise NotImplementedError

    def uninstall(self, game_id):
        raise NotImplementedError

    def launch(self, game_id, env=None):
        """Start a game. env adds variables for the game's process. Returns
        its Popen, or None when another client (Steam) starts it for us or
        its cloud saves download first."""
        raise NotImplementedError
