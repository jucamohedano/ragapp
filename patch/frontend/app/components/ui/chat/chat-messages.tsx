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

// Function to delete the collection
const deleteCollection = async (collectionName: string) => {
  try {
    await client.deleteCollection(collectionName);
    console.log(`Collection '${collectionName}' deleted successfully.`);
  } catch (error) {
    console.error(`Error deleting collection '${collectionName}':`, error);
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
      const fileUrl = latestPoint.payload?.['fileUrl'] as string | undefined;

      if (latestInfo === "Results-LLM.xlsx") {
        console.log("Results-LLM.xlsx");
        // Delete the 'events' collection
        await deleteCollection("events");
      } else {
        console.log("Not Results-LLM.xlsx");
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
        

        console.log("title: ", latestInfo);
        console.log("fileUrl: ", fileUrl);

        const eventData: EventData = {
          title: latestInfo,
          isCollapsed: false,
          fileUrl: fileUrl, // Set the fileUrl in the EventData
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
  const [fileUrl, setFileUrl] = useState<string | null>("/api/chat/download"); // State to hold the file URL
  
  
useEffect(() => {
  if (shouldFetch) {
    setIsLoading(true);
    intervalRef.current = setInterval(() => {
      fetchLatestPoint(setData, setError, setFileUrl);
    }, 500); // Fetch every 1 second (was 0.5, which is too frequent)
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
  
  // State to store value from ChatEvents
  const [fileDownloaded, setfileDownloaded] = useState<any>(null);

  const handlefileDownloaded = (value: any) => {
    setfileDownloaded(value);
    // You can perform additional actions with the received value here
  };

  const { data: eventData, isLoading: eventLoading, error, fileUrl } = useQdrant(
    isPending
  );

  // Log values for debugging
  // console.log('isPending:', isPending);
  // console.log('fileDownloaded:', fileDownloaded);


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
      {/* {isPending || (<ChatEvents data={eventData} isLoading={eventLoading} onValueChange={handlefileDownloaded}/>)} */}
      {(isPending || !fileDownloaded) && (
      <ChatEvents
        data={eventData}
        isLoading={eventLoading}
        onValueChange={handlefileDownloaded}
      />
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