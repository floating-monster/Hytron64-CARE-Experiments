package chipyard

import org.chipsalliance.cde.config.Config
import freechips.rocketchip.rocket._

class Hytron64SmallCARE2PConfig extends Config(
  new freechips.rocketchip.subsystem.WithoutTLMonitors ++
  new WithNSmallCores(4) ++
  new chipyard.config.AbstractConfig
)
