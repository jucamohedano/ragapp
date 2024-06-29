import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "../button";
import ChatActions from "./chat-actions";
import ChatMessage from "./chat-message";
import { ChatHandler } from "./chat.interface";
import { useClientConfig } from "./hooks/use-config";
import { ChatEvents } from "./chat-message/chat-events";
import { EventData } from "./index";
import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

// interface Collection {
//   name: string;
//   // Add other properties if needed
// }


// Function to delete the collection
const deleteCollection = async (collectionName: string) => {
  try {
    await client.deleteCollection(collectionName);
    console.log(`Collection '${collectionName}' deleted successfully.`);
  } catch (error) {
    console.error(`Error deleting collection '${collectionName}':`, error);
  }
};

const checkAndDeleteCollection = async (collectionName: string) => {
  try {
    // Check if the collection exists
    const collectionExists = await client.collectionExists(collectionName);

    if (collectionExists) {
      // Delete the collection
      await client.deleteCollection(collectionName);
      console.log(`Collection '${collectionName}' deleted successfully.`);
    } else {
      console.warn(`Collection '${collectionName}' does not exist.`);
    }
  } catch (error) {
    console.error(`Error checking/deleting collection '${collectionName}':`, error);
    // Handle error as needed, e.g., set an error state
  }
};

const fetchLatestPoint = async (
  setData: React.Dispatch<React.SetStateAction<EventData[]>>,
  setError: React.Dispatch<React.SetStateAction<string | null>>,
  setFileUrl: React.Dispatch<React.SetStateAction<string | null>>
) => {
  try {
    const collectionsResponse = await client.getCollections();
    const collectionExists = collectionsResponse.collections.some(
      (collection) => collection.name === "events"
    );

    if (!collectionExists) {
      console.warn("Collection 'events' does not exist.");
      return;
    }

    const response = await client.scroll("events", {
      limit: 1000, // Fetch up to 1000 points (adjust as needed)
      with_payload: true,
      with_vector: false,
    });

    // console.log("Qdrant response:", response);

    if (response.points.length > 0) {
      const allPoints = response.points;
      const latestPoint = allPoints[allPoints.length - 1];
      const latestInfo = latestPoint.payload?.['Event Text'] as string | undefined;

      if (latestInfo === "Results-LLM.xlsx") {
        console.log("Results-LLM.xlsx");
        // Set the file URL for the download link
        setFileUrl("/api/chat/download"); // Assuming your backend endpoint is at /download

        // Delete the 'events' collection
        await deleteCollection("events");
      } else {
        console.log("Not Results-LLM.xlsx");
        setFileUrl(null); // Reset the file URL if condition is not met
      }
    

      if (!latestInfo) {
        console.warn("Latest point does not contain 'Event Text'.");
        return;
      }

      // Check if the latest point is the same as the last one in state
      setData(prevData => {
        const lastEventData = prevData[prevData.length - 1];

        if (lastEventData && lastEventData.title === latestInfo) {
          console.log("Skipping duplicate point.");
          return prevData;
        }

        const eventData: EventData = {
          title: latestInfo,
          isCollapsed: true,
        };

        return [...prevData, eventData];
      });
    } else {
      console.warn("Collection 'events' is empty.");
    }
  } catch (error) {
    console.error("Error fetching latest point from Qdrant:", error);
    setError("Error fetching latest point from Qdrant");
  }
};

const useQdrant = (shouldFetch: boolean) => {
  const [data, setData] = useState<EventData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout>(); // Ref for interval
  const [fileUrl, setFileUrl] = useState<string | null>(null); // State to hold the file URL
  
  
useEffect(() => {
  if (shouldFetch) {
    setIsLoading(true);
    intervalRef.current = setInterval(() => {
      fetchLatestPoint(setData, setError, setFileUrl);
    }, 1000); // Fetch every 1 second (was 0.5, which is too frequent)
  } else {
    setIsLoading(false);
    if (intervalRef.current) clearInterval(intervalRef.current);
  }

  return () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
  };
}, [shouldFetch]);

return { data, isLoading, error, fileUrl };
};

const useWebSocket = (url: string, shouldConnect: boolean) => {
  const [data, setData] = useState<EventData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (shouldConnect) {
      const socket = new WebSocket(url);
      socketRef.current = socket;

      setIsLoading(true);

      socket.onopen = () => {
        console.log('WebSocket connection established');
      };

      socket.onmessage = (event) => {
        try {
          console.log("WebSocket message received:", event);
          const eventData: EventData[] = JSON.parse(event.data);
          console.log("Parsed WebSocket message data:", eventData);
          setData(eventData);
        } catch (parseError) {
          console.error('Error parsing WebSocket message:', parseError);
          setError('Error parsing WebSocket message');
        }
      };

      socket.onerror = (errorEvent) => {
        console.error('WebSocket error:', errorEvent);
        setError('WebSocket connection error');
        setIsLoading(false);
      };

      socket.onclose = () => {
        console.log('WebSocket connection closed');
        setIsLoading(false);
      };
    } else {
      // Close the socket if shouldConnect becomes false
      if (socketRef.current) {
        console.log('Closing WebSocket connection due to shouldConnect being false');
        socketRef.current.close();
        socketRef.current = null;
        setIsLoading(false);
      }
    }

    // Clean-up function
    return () => {
      if (socketRef.current) {
        console.log('Closing WebSocket connection during cleanup');
        socketRef.current.close();
        socketRef.current = null;
        setIsLoading(false);
      }
    };
  }, [url, shouldConnect]);

  return { data, isLoading, error };
};

export default function ChatMessages(
  props: Pick<
    ChatHandler,
    "messages" | "isLoading" | "reload" | "stop" | "append"
  >,
) {
  const { starterQuestions } = useClientConfig();
  const scrollableChatContainerRef = useRef<HTMLDivElement>(null);
  const messageLength = props.messages.length;
  const lastMessage = props.messages[messageLength - 1];

  const scrollToBottom = () => {
    if (scrollableChatContainerRef.current) {
      scrollableChatContainerRef.current.scrollTop =
        scrollableChatContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messageLength, lastMessage]);

  const isLastMessageFromAssistant =
    messageLength > 0 && lastMessage?.role !== "user";
  const showReload =
    props.reload && !props.isLoading && isLastMessageFromAssistant;
  const showStop = props.stop && props.isLoading;

  const isPending = props.isLoading && !isLastMessageFromAssistant;
  
  const { data: eventData, isLoading: eventLoading, error, fileUrl } = useQdrant(
    isPending
  );

  return (
    <div
      className="flex-1 w-full rounded-xl bg-white p-4 shadow-xl relative overflow-y-auto"
      ref={scrollableChatContainerRef}
    >
      <div className="flex flex-col gap-5 divide-y">
        {props.messages.map((m, i) => {
          const isLoadingMessage = i === messageLength - 1 && props.isLoading;
          return (
            <ChatMessage
              key={m.id}
              chatMessage={m}
              isLoading={isLoadingMessage}
            />
          );
        })}
        {/* {isPending && (
          <div className="flex justify-center items-center pt-10">
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
        )} */}
      </div>
      {isPending && (<ChatEvents data={eventData} isLoading={eventLoading} />)}
      {fileUrl && (
        <div className="mt-4">
          <a href={fileUrl} download="Results-LLM.xlsx" className="text-blue-500 underline">
            Download Results-LLM.xlsx
          </a>
        </div>
      )}
      {(showReload || showStop) && (
        <div className="flex justify-end py-4">
          <ChatActions
            reload={props.reload}
            stop={props.stop}
            showReload={showReload}
            showStop={showStop}
          />
        </div>
      )}
      {!messageLength && starterQuestions?.length && props.append && (
        <div className="absolute bottom-6 left-0 w-full">
          <div className="grid grid-cols-2 gap-2 mx-20">
            {starterQuestions.map((question, i) => (
              <Button
                variant="outline"
                key={i}
                onClick={() =>
                  props.append!({ role: "user", content: question })
                }
              >
                {question}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}