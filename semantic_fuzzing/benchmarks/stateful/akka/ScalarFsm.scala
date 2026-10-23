package stateful.scalarFsm
import akka.actor._

sealed trait Phase
case object Idle extends Phase
case object Active extends Phase
final case class Open(amount: Int)
final case class Add(amount: Int)
case object Close
case object Reset
final case class Notice(value: Int)

final class Worker(client: ActorRef) extends FSM[Phase, Int] {
  private var transitions: Int = 0
  private var oldData: Int = 0
  startWith(Idle, 0)
  when(Idle) {
    case Event(Open(amount), data) => goto(Active) using (data + amount)
  }
  when(Active) {
    case Event(Add(amount), data) => stay using (data + amount)
    case Event(Open(amount), data) => goto(Active) using (data + amount)
    case Event(Close, data) => goto(Idle) using data
  }
  whenUnhandled {
    case Event(Reset, _) => stay using 0
    case Event(Add(_), _) => stay
    case Event(Close, _) => stay
  }
  onTransition {
    case _ -> Active =>
      transitions += 1
      oldData = stateData
      client ! Notice(nextStateData)
    case Active -> Idle =>
      transitions += 1
      oldData = stateData
      client ! Notice(nextStateData)
  }
  initialize()
}
final class Client extends Actor {
  private var notices: Int = 0
  private var last: Int = 0
  def receive: Receive = {
    case Notice(value) => notices += 1; last = value
  }
}
object ScalarFsm extends App {
  val system = ActorSystem("ScalarFsm")
  val client = system.actorOf(Props[Client](), "client")
  val worker = system.actorOf(Props(new Worker(client)), "worker")
}
