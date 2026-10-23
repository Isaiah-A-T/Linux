PREFIX ?= /usr/local
DESTDIR ?=
PYTHON ?= python3

.PHONY: dev test install

# Run the shell against mock data, then open http://127.0.0.1:7777/
dev:
	LUMEN_MOCK=1 PYTHONPATH=shell $(PYTHON) -m lumend --ui shell/ui

test:
	PYTHONPATH=shell $(PYTHON) -m unittest discover -s tests -t . -v

install:
	install -d $(DESTDIR)$(PREFIX)/lib/lumen $(DESTDIR)$(PREFIX)/share/lumen
	cp -r shell/lumend $(DESTDIR)$(PREFIX)/lib/lumen/
	find $(DESTDIR)$(PREFIX)/lib/lumen -name __pycache__ -prune -exec rm -rf {} +
	cp -r shell/ui $(DESTDIR)$(PREFIX)/share/lumen/
	install -Dm755 session/lumen-session $(DESTDIR)$(PREFIX)/bin/lumen-session
	install -Dm755 session/lumen-greeter $(DESTDIR)$(PREFIX)/bin/lumen-greeter
	install -Dm755 session/lumen-ui $(DESTDIR)$(PREFIX)/bin/lumen-ui
	install -Dm755 session/lumend $(DESTDIR)$(PREFIX)/bin/lumend
	install -Dm755 session/lumen-update-system $(DESTDIR)$(PREFIX)/lib/lumen/lumen-update-system
	install -Dm644 session/lumend.service $(DESTDIR)$(PREFIX)/lib/systemd/user/lumend.service
	install -Dm644 session/lumen-auto-update.service $(DESTDIR)$(PREFIX)/lib/systemd/system/lumen-auto-update.service
	install -Dm644 session/lumen-auto-update.timer $(DESTDIR)$(PREFIX)/lib/systemd/system/lumen-auto-update.timer
# Enabled by the package itself, so systems that update to this version get
# automatic updates without a setup step. AUTO_UPDATE=off turns them off.
	install -d $(DESTDIR)$(PREFIX)/lib/systemd/system/timers.target.wants
	ln -sf ../lumen-auto-update.timer $(DESTDIR)$(PREFIX)/lib/systemd/system/timers.target.wants/lumen-auto-update.timer
	install -Dm644 session/polkit/50-lumen.rules $(DESTDIR)$(PREFIX)/share/polkit-1/rules.d/50-lumen.rules
	install -Dm644 session/polkit/org.lumenos.update.policy $(DESTDIR)$(PREFIX)/share/polkit-1/actions/org.lumenos.update.policy
	install -Dm644 session/lumen.desktop $(DESTDIR)$(PREFIX)/share/wayland-sessions/lumen.desktop
