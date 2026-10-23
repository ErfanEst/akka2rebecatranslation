package semanticExamples.behaviorStack
import akka.actor._

case object PushActive
case object PushPaused
case object ReplaceActive
case object Pop
final case class Add(amount: Int)
case object Noop

final class ModeActor extends Actor {
  private var value: Int = 0
  def receive: Receive = {
    case PushActive => context.become(active, discardOld = false)
    case PushPaused => context.become(paused, discardOld = false)
    case ReplaceActive => context.become(active)
    case Pop => context.unbecome()
    case Add(amount) => value += amount
  }
  def active: Receive = {
    case PushActive => context.become(active, discardOld = false)
    case PushPaused => context.become(paused, discardOld = false)
    case ReplaceActive => context.become(active)
    case Pop => context.unbecome()
    case Add(amount) => value += amount * 2
  }
  def paused: Receive = {
    case PushActive => context.become(active, discardOld = false)
    case PushPaused => context.become(paused, discardOld = false)
    case ReplaceActive => context.become(active)
    case Pop => context.unbecome()
    case Add(amount) => ()
  }
}
final class Client(worker: ActorRef) extends Actor {
  def receive: Receive = { case Noop => () }
}
object BehaviorStack extends App {
  val system = ActorSystem("BehaviorStack")
  val worker = system.actorOf(Props[ModeActor](), name = "worker")
  val client = system.actorOf(Props(new Client(worker)), name = "client")
}
