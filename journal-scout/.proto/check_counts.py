import sys

sys.path.insert(0, "src")

from josc.server import TOOL_NAMES
from josc.providers import provider_names, search_provider_names
import josc.exporters as ex

print("providers:", len(provider_names()), sorted(provider_names()))
print("searchable:", len(search_provider_names()), sorted(search_provider_names()))
print("tools:", len(TOOL_NAMES))
print("formatters:", len(ex.FORMATTERS), sorted(ex.FORMATTERS))
