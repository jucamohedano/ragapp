import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";
import { Button } from "../../button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "../../collapsible";
import { EventData } from "../index";

// export function ChatEvents({
//   data,
//   isLoading,
// }: {
//   data: EventData[];
//   isLoading: boolean;
// }) {
//   const [isOpen, setIsOpen] = useState(false);

//   const buttonLabel = isOpen ? "Hide events" : "Show events";

//   const EventIcon = isOpen ? (
//     <ChevronDown className="h-4 w-4" />
//   ) : (
//     <ChevronRight className="h-4 w-4" />
//   );

//   return (
//     <div className="border-l-2 border-indigo-400 pl-2">
//       <Collapsible open={isOpen} onOpenChange={setIsOpen}>
//         <CollapsibleTrigger asChild>
//           <Button variant="secondary" className="space-x-2">
//             {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
//             <span>{buttonLabel}</span>
//             {EventIcon}
//           </Button>
//         </CollapsibleTrigger>
//         <CollapsibleContent asChild>
//           <div className="mt-4 text-sm space-y-2">
//             {data.map((eventItem, index) => (
//               <div className="whitespace-break-spaces" key={index}>
//                 {eventItem.title}
//               </div>
//             ))}
//           </div>
//         </CollapsibleContent>
//       </Collapsible>
//     </div>
//   );
// }


// WORKING VERSION OF THE URL
// export function ChatEvents({
//   data,
//   isLoading,
// }: {
//   data: EventData[];
//   isLoading: boolean;
// }) {
//   const [isOpen, setIsOpen] = useState(false);

//   const buttonLabel = isOpen ? "Hide events" : "Show events";

//   const EventIcon = isOpen ? (
//     <ChevronDown className="h-4 w-4" />
//   ) : (
//     <ChevronRight className="h-4 w-4" />
//   );

//   return (
//     <div className="border-l-2 border-indigo-400 pl-2">
//       <Collapsible open={isOpen} onOpenChange={setIsOpen}>
//         <CollapsibleTrigger asChild>
//           <Button variant="secondary" className="space-x-2">
//             {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
//             <span>{buttonLabel}</span>
//             {EventIcon}
//           </Button>
//         </CollapsibleTrigger>
//         <CollapsibleContent asChild>
//           <div className="mt-4 text-sm space-y-2">
//             {data.map((eventItem, index) => (
//               <div className="whitespace-break-spaces" key={index}>
//                 {eventItem.title}
//                 {eventItem.fileUrl && (
//                   <div className="mt-2">
//                     <a href={eventItem.fileUrl} download="Results-LLM.xlsx" className="text-blue-500 underline">
//                       Download Results-LLM.xlsx
//                     </a>
//                   </div>
//                 )}
//               </div>
//             ))}
//           </div>
//         </CollapsibleContent>
//       </Collapsible>
//     </div>
//   );
// }



// WORKING VERSION OF THE URL 2
// export function ChatEvents({
//   data,
//   isLoading,
// }: {
//   data: EventData[];
//   isLoading: boolean;
// }) {

type ChatEventsProps = {
  data: EventData[];
  isLoading: boolean;
  onValueChange?: (value: any) => void; // Make onValueChange optional
};

  // export function ChatEvents({
  //   data,
  //   isLoading,
  //   onValueChange,
  // }: {
  //   data: EventData[];
  //   isLoading: boolean;
  //   onValueChange: (value: any) => void; // Define the function type
  // }) {
  export function ChatEvents({
    data,
    isLoading,
    onValueChange = () => {}, // Default to an empty function if not provided
  }: ChatEventsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [fileDownloaded, setFileDownloaded] = useState(false);

  const buttonLabel = isOpen ? "Hide events" : "Show events";

  const EventIcon = isOpen ? (
    <ChevronDown className="h-4 w-4" />
  ) : (
    <ChevronRight className="h-4 w-4" />
  );

  useEffect(() => {
    // Automatically open the collapsible if there's a file URL and it hasn't been downloaded
    const hasFileUrl = data.some(eventItem => eventItem.fileUrl);
    if (hasFileUrl && !fileDownloaded) {
      setIsOpen(true);
    }
  }, [data, fileDownloaded]);

  const handleDownloadClick = () => {
    setFileDownloaded(true);
    // Notify parent component (ChatMessages) about the download completion
    if (onValueChange) {
      onValueChange(true);
    } 
  };

  return (
    <div className="border-l-2 border-indigo-400 pl-2">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="secondary" className="space-x-2">
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            <span>{buttonLabel}</span>
            {EventIcon}
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent asChild>
          <div className="mt-4 text-sm space-y-2">
            {data.map((eventItem, index) => (
              <div className="whitespace-break-spaces" key={index}>
                {eventItem.title}
                {eventItem.fileUrl && (
                  <div className="mt-2">
                    Task completed. Report is available for
                     <a
                      href={eventItem.fileUrl}
                      download="Results-LLM.xlsx"
                      className="text-blue-500 underline"
                      onClick={handleDownloadClick}
                    >
                       download
                      {/* Download Results-LLM.xlsx */}
                    </a>.
                  </div>
                )}
              </div>
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}





// export function ChatEvents({
//   data,
//   isLoading,
// }: {
//   data: EventData[];
//   isLoading: boolean;
// }) {
//   const [isOpen, setIsOpen] = useState(false);
//   const [fileDownloaded, setFileDownloaded] = useState(false);

//   const buttonLabel = isOpen ? "Hide events" : "Show events";

//   const EventIcon = isOpen ? (
//     <ChevronDown className="h-4 w-4" />
//   ) : (
//     <ChevronRight className="h-4 w-4" />
//   );

//   useEffect(() => {
//     // Automatically open the collapsible if there's a file URL and it hasn't been downloaded
//     const hasFileUrl = data.some((eventItem) => eventItem.fileUrl);
//     if (hasFileUrl && !fileDownloaded) {
//       setIsOpen(true);
//     }
//   }, [data, fileDownloaded]);

//   const handleDownloadClick = () => {
//     setFileDownloaded(true);
//     // Leave isOpen as true so that ChatEvents remains open after download
//   };

//   // Ensure that ChatEvents remains rendered until file is downloaded
//   if (!fileDownloaded) {
//     return (
//       <div className="border-l-2 border-indigo-400 pl-2">
//         <Collapsible open={isOpen} onOpenChange={setIsOpen}>
//           <CollapsibleTrigger asChild>
//             <Button variant="secondary" className="space-x-2">
//               {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
//               <span>{buttonLabel}</span>
//               {EventIcon}
//             </Button>
//           </CollapsibleTrigger>
//           <CollapsibleContent asChild>
//             <div className="mt-4 text-sm space-y-2">
//               {data.map((eventItem, index) => (
//                 <div className="whitespace-break-spaces" key={index}>
//                   {eventItem.title}
//                   {eventItem.fileUrl && (
//                     <div className="mt-2">
//                       Task completed. Report is available for{" "}
//                       <a
//                         href={eventItem.fileUrl}
//                         download="Results-LLM.xlsx"
//                         className="text-blue-500 underline"
//                         onClick={handleDownloadClick}
//                       >
//                         download
//                         {/* Download Results-LLM.xlsx */}
//                       </a>
//                       .
//                     </div>
//                   )}
//                 </div>
//               ))}
//             </div>
//           </CollapsibleContent>
//         </Collapsible>
//       </div>
//     );
//   } else {
//     // Return null or any fallback if you want ChatEvents to disappear after download
//     return null;
//   }
// }
















// import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
// import { useState } from "react";
// import { Button } from "../../button";
// import {
//   Collapsible,
//   CollapsibleContent,
//   CollapsibleTrigger,
// } from "../../collapsible";
// import { EventData } from "../index";

// export function ChatEvents({
//   data,
//   isLoading,
// }: {
//   data: EventData[];
//   isLoading: boolean;
// }) {
//   const [isOpen, setIsOpen] = useState(false);

//   const buttonLabel = isOpen ? "Hide events" : "Show events";

//   const EventIcon = isOpen ? (
//     <ChevronDown className="h-4 w-4" />
//   ) : (
//     <ChevronRight className="h-4 w-4" />
//   );

//   return (
//     <div className="border-l-2 border-indigo-400 pl-2">
//       <Collapsible open={isOpen} onOpenChange={setIsOpen}>
//         <CollapsibleTrigger asChild>
//           <Button variant="secondary" className="space-x-2">
//             {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
//             <span>{buttonLabel}</span>
//             {EventIcon}
//           </Button>
//         </CollapsibleTrigger>
//         <CollapsibleContent asChild>
//           <div className="mt-4 text-sm space-y-2">
//             {data.map((eventItem, index) => (
//               <div className="whitespace-break-spaces" key={index}>
//                 {eventItem.title}
//                 {eventItem.downloadUrl && (
//                   <div>
//                     <a href={eventItem.downloadUrl} download>
//                       Download File
//                     </a>
//                   </div>
//                 )}
//               </div>
//             ))}
//           </div>
//         </CollapsibleContent>
//       </Collapsible>
//     </div>
//   );
// }
