import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
	Brain,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	FileText,
	Plus,
	Trash2,
	Loader2,
	TriangleAlert,
} from "lucide-react";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";

import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

interface OmegaConfigModalProps {
	isOpen: boolean;
	onClose: () => void;
}

type SubjectConfig = {
	sections: {
		[key: string]: {
			marks: number;
			negative_marks: number;
			start_q: number;
			end_q: number;
			type: "SCQ" | "MCQ" | "NUMERIC" | "INTEGER";
		};
	};
};

type ConfigState = {
	title: string;
	duration: number;
	scheduledAt: string;
	standard: string;
	category: string;
	subjects: {
		[key: string]: SubjectConfig;
	};
};

// Initial State Helper
const INITIAL_CONFIG: ConfigState = {
	title: "",
	duration: 180,
	scheduledAt: "",
	standard: "12th",
	category: "JEE Mains",
	subjects: {
		Physics: {
			sections: {
				"Section A": { marks: 4, negative_marks: -1, start_q: 1, end_q: 20, type: "SCQ" },
			},
		},
		Chemistry: {
			sections: {
				"Section A": { marks: 4, negative_marks: -1, start_q: 21, end_q: 40, type: "SCQ" },
			},
		},
		Mathematics: {
			sections: {
				"Section A": { marks: 4, negative_marks: -1, start_q: 41, end_q: 60, type: "SCQ" },
			},
		},
	},
};

export default function OmegaConfigModal({
	isOpen,
	onClose,
}: OmegaConfigModalProps) {
	const queryClient = useQueryClient();
	const [step, setStep] = useState<
		"upload" | "config" | "processing" | "success"
	>("upload");
	const [file, setFile] = useState<File | null>(null);
	const [config, setConfig] = useState<ConfigState>(INITIAL_CONFIG);
	const [subjectOrder, setSubjectOrder] = useState<string[]>(Object.keys(INITIAL_CONFIG.subjects));
	const [parsingReport, setParsingReport] = useState<any>(null);

	// Progress Tracking State
	const [jobId, setJobId] = useState<string | null>(null);
	const [progress, setProgress] = useState(0);
	const [statusMessage, setStatusMessage] = useState("Preparing upload...");

	// Polling Effect (Category Swap)
	useEffect(() => {
		if (config.category === "NEET") {
			if (config.subjects["Mathematics"]) {
				const newSubjects = { ...config.subjects };
				newSubjects["Biology"] = newSubjects["Mathematics"];
				delete newSubjects["Mathematics"];
				setConfig((prev) => ({ ...prev, subjects: newSubjects }));
				setSubjectOrder((prev) => prev.map((s) => (s === "Mathematics" ? "Biology" : s)));
			}
		} else {
			if (config.subjects["Biology"]) {
				const newSubjects = { ...config.subjects };
				newSubjects["Mathematics"] = newSubjects["Biology"];
				delete newSubjects["Biology"];
				setConfig((prev) => ({ ...prev, subjects: newSubjects }));
				setSubjectOrder((prev) => prev.map((s) => (s === "Biology" ? "Mathematics" : s)));
			}
		}
	}, [config.category, config.subjects]);

	// Recalculates start_q and end_q based on the current subjectOrder
	const recalculateChronology = (order: string[]) => {
		setConfig((prev) => {
			let currentQuestionNumber = 1;
			const newSubjects = { ...prev.subjects };

			order.forEach((subject) => {
				if (!newSubjects[subject]) return;
				const sections = { ...newSubjects[subject].sections };
				Object.keys(sections).forEach((sectionName) => {
					const sec = sections[sectionName];
					const start = typeof sec.start_q === 'number' ? sec.start_q : parseInt(sec.start_q as string, 10);
					const end = typeof sec.end_q === 'number' ? sec.end_q : parseInt(sec.end_q as string, 10);
					const rangeSize = end - start + 1;
					
					// Reassign strictly as numbers to satisfy SubjectConfig
					sec.start_q = currentQuestionNumber;
					sec.end_q = currentQuestionNumber + rangeSize - 1;
					
					currentQuestionNumber += rangeSize;
				});
				newSubjects[subject] = { ...newSubjects[subject], sections };
			});

			return { ...prev, subjects: newSubjects };
		});
	};

	const moveSubject = (subject: string, direction: "up" | "down") => {
		setSubjectOrder((prev) => {
			const idx = prev.indexOf(subject);
			if (idx === -1) return prev;
			if (direction === "up" && idx === 0) return prev;
			if (direction === "down" && idx === prev.length - 1) return prev;

			const newOrder = [...prev];
			const swapIdx = direction === "up" ? idx - 1 : idx + 1;
			[newOrder[idx], newOrder[swapIdx]] = [newOrder[swapIdx], newOrder[idx]];
			
			// Trigger strict recalibration sequentially according to the new layout
			requestAnimationFrame(() => recalculateChronology(newOrder));
			return newOrder;
		});
	};

	// Polling Effect
	useEffect(() => {
		let interval: any;
		if (jobId && step === "processing") {
			interval = setInterval(async () => {
				try {
					const token = localStorage.getItem("access_token");
					const response = await fetch(
						`${import.meta.env.VITE_API_URL}/api/v1/omega/progress/${jobId}`,
						{
							headers: { Authorization: `Bearer ${token}` },
						},
					);
					if (response.ok) {
						const data = await response.json();
						setProgress(data.progress || 0);
						setStatusMessage(data.message || "Processing...");

						if (data.status === "completed") {
							setParsingReport(data.result);
							setStep("success");
							setJobId(null);
							queryClient.invalidateQueries({ queryKey: ["tests"] });
						} else if (data.status === "failed") {
							alert(`AI Processing Failed: ${data.message}`);
							setStep("config");
							setJobId(null);
						}
					}
				} catch (err) {
					console.error("Polling error:", err);
				}
			}, 2000);
		}
		return () => clearInterval(interval);
	}, [jobId, step, queryClient]);

	const uploadMutation = useMutation({
		mutationFn: async () => {
			const formData = new FormData();

			formData.append("file", file!);
			
			// Establish Strict Chronological Order based on user's manual sort
			const orderedSubjects: { [key: string]: any } = {};
			subjectOrder.forEach((sub) => {
				if (config.subjects[sub]) {
					orderedSubjects[sub] = config.subjects[sub];
				}
			});
			const payloadConfig = { ...config, subjects: orderedSubjects };
			formData.append("config", JSON.stringify(payloadConfig));

			const token = localStorage.getItem("access_token");
			console.log("Starting upload...", { file: file?.name, config });

			const response = await fetch(
				`${import.meta.env.VITE_API_URL}/api/v1/omega/upload`,
				{
					method: "POST",
					headers: { Authorization: `Bearer ${token}` },
					body: formData,
				},
			);

			if (!response.ok) {
				const err = await response.json();
				console.error("Upload failed response:", err);
				throw new Error(err.detail || "Upload failed");
			}
			return response.json();
		},
		onSuccess: (data) => {
			console.log("Upload initiated:", data);
			if (data.job_id) {
				setJobId(data.job_id);
			} else {
				// Fallback for legacy or cached hits (though backend now handles cache via jobs too)
				setParsingReport(data);
				setStep("success");
				queryClient.invalidateQueries({ queryKey: ["tests"] });
			}
		},
		onError: (error: any) => {
			console.error("Mutation error:", error);

			// Specifically handle 429 Too Many Requests (Rate Limit)
			if (
				error.message.includes("429") ||
				error.message.includes("LIMIT REACHED")
			) {
				alert("DAILY LIMIT REACHED, PLEASE TRY TOMORROW");
			} else {
				alert(`Error: ${error.message}`);
			}

			// Revert from processing state to allow retry or checking config
			setStep("config");
		},
	});

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		if (e.target.files?.[0]) {
			console.log("File selected:", e.target.files[0].name);
			setFile(e.target.files[0]);

			// Auto-set title from filename if empty
			if (!config.title) {
				setConfig((prev) => ({
					...prev,
					title: e.target.files![0].name.replace(".pdf", ""),
				}));
			}

			// Auto-advance to config
			setStep("config");
		}
	};

	const handleSectionChange = (
		subject: string,
		section: string,
		field: string,
		value: string,
	) => {
		setConfig((prev) => ({
			...prev,
			subjects: {
				...prev.subjects,
				[subject]: {
					...prev.subjects[subject],
					sections: {
						...prev.subjects[subject].sections,
						[section]: {
							...prev.subjects[subject].sections[section],
							[field]: field === "type" ? value : parseFloat(value) || 0,
						},
					},
				},
			},
		}));
	};

	const addSection = (subject: string) => {
		const qCountStr = window.prompt(`How many questions should the new section for ${subject} contain?`, "20");
		if (!qCountStr) return;
		
		const qCount = parseInt(qCountStr, 10);
		if (Number.isNaN(qCount) || qCount <= 0) {
			alert("Please enter a valid positive number for question count.");
			return;
		}

		const newSectionName = `Section ${String.fromCharCode(65 + Object.keys(config.subjects[subject].sections).length)}`;
		setConfig((prev) => ({
			...prev,
			subjects: {
				...prev.subjects,
				[subject]: {
					...prev.subjects[subject],
					sections: {
						...prev.subjects[subject].sections,
						[newSectionName]: {
							marks: 4,
							negative_marks: -1,
							start_q: 1,
							end_q: qCount,
							type: "SCQ",
						},
					},
				},
			},
		}));
		
		// Immediately auto-calculate boundaries based on new sizing
		requestAnimationFrame(() => recalculateChronology(subjectOrder));
	};

	const removeSection = (subject: string, section: string) => {
		const newSections = { ...config.subjects[subject].sections };
		delete newSections[section];
		setConfig((prev) => ({
			...prev,
			subjects: {
				...prev.subjects,
				[subject]: {
					...prev.subjects[subject],
					sections: newSections,
				},
			},
		}));
		
		requestAnimationFrame(() => recalculateChronology(subjectOrder));
	};

	const handleSubmit = () => {
		if (!file || !config.title) return;
		setStep("processing");
		uploadMutation.mutate();
	};

	const reset = () => {
		setStep("upload");
		setFile(null);
		setConfig(INITIAL_CONFIG);
		setParsingReport(null);
		onClose();
	};

	return (
		<Dialog open={isOpen} onOpenChange={reset}>
			<DialogContent className="sm:max-w-2xl bg-zinc-950 border-white/10 text-white max-h-[90vh] flex flex-col">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2 text-xl">
						<Brain className="text-purple-500" /> Omega Go: Smart Generate
					</DialogTitle>
					<DialogDescription className="text-zinc-400">
						Upload a PDF question paper and let AI generate the test for you.
					</DialogDescription>
				</DialogHeader>

				<div className="flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-6 py-4">
					{step === "upload" && (
						<div className="flex flex-col items-center justify-center border-2 border-dashed border-zinc-700 rounded-xl p-10 gap-4 hover:bg-zinc-900/50 transition-colors cursor-pointer relative">
							<input
								type="file"
								accept="application/pdf"
								onChange={handleFileChange}
								className="absolute inset-0 opacity-0 cursor-pointer"
							/>
							<div className="bg-zinc-800 p-4 rounded-full">
								<FileText className="size-8 text-zinc-400" />
							</div>
							<div className="text-center">
								<p className="font-medium text-lg">
									{file ? file.name : "Click to Upload PDF"}
								</p>
								<p className="text-sm text-zinc-500">
									{file
										? `${(file.size / 1024 / 1024).toFixed(2)} MB`
										: "Drag & drop or click to browse"}
								</p>
							</div>
						</div>
					)}

					{step === "config" && (
						<div className="space-y-6">
							<div className="grid grid-cols-2 gap-4">
								<div className="col-span-2 space-y-2">
									<Label>Test Title</Label>
									<Input
										value={config.title}
										onChange={(e) =>
											setConfig({ ...config, title: e.target.value })
										}
										className="bg-zinc-900 border-white/10"
										placeholder="e.g. JEE Main Mock Test 1"
									/>
								</div>
								<div className="space-y-2">
									<Label>Duration (Minutes)</Label>
									<Input
										type="number"
										value={config.duration}
										onChange={(e) =>
											setConfig({
												...config,
												duration: parseInt(e.target.value, 10) || 0,
											})
										}
										className="bg-zinc-900 border-white/10"
									/>
								</div>
								<div className="space-y-2">
									<Label>Scheduled Time (Optional)</Label>
									<Input
										type="datetime-local"
										value={config.scheduledAt}
										onChange={(e) =>
											setConfig({ ...config, scheduledAt: e.target.value })
										}
										className="bg-zinc-900 border-white/10"
									/>
								</div>
								<div className="space-y-2">
									<Label>Class / Standard</Label>
									<Select
										value={config.standard}
										onValueChange={(val) =>
											setConfig({ ...config, standard: val })
										}
									>
										<SelectTrigger className="bg-zinc-900 border-white/10">
											<SelectValue placeholder="Select Class" />
										</SelectTrigger>
										<SelectContent className="bg-zinc-900 border-zinc-800 text-white">
											<SelectItem value="11th">11th Class</SelectItem>
											<SelectItem value="12th">12th Class</SelectItem>
											<SelectItem value="Dropper">Dropper</SelectItem>
										</SelectContent>
									</Select>
								</div>
								<div className="space-y-2">
									<Label>Stream / Exam</Label>
									<Select
										value={config.category}
										onValueChange={(val) =>
											setConfig({ ...config, category: val })
										}
									>
										<SelectTrigger className="bg-zinc-900 border-white/10">
											<SelectValue placeholder="Select Exam" />
										</SelectTrigger>
										<SelectContent className="bg-zinc-900 border-zinc-800 text-white">
											<SelectItem value="JEE Mains">JEE Mains</SelectItem>
											<SelectItem value="JEE Advanced">JEE Advanced</SelectItem>
											<SelectItem value="NEET">NEET</SelectItem>
											<SelectItem value="Foundation">Foundation</SelectItem>
										</SelectContent>
									</Select>
								</div>
							</div>

							<div className="space-y-4">
								<h3 className="font-semibold text-lg text-purple-400">
									Subject Configuration
								</h3>
								{subjectOrder.map((subject, index) => {
									const subConfig = config.subjects[subject];
									if (!subConfig) return null;
									return (
									<Card
										key={subject}
										className="bg-zinc-900/50 border-white/10"
									>
										<CardContent className="p-4 space-y-4">
											<div className="flex items-center justify-between">
												<div className="flex items-center gap-3">
													<h4 className="font-bold text-zinc-200">{subject}</h4>
													<div className="flex items-center gap-1 opacity-50 hover:opacity-100 transition-opacity">
														<Button
															variant="ghost"
															size="icon"
															className="h-6 w-6 text-zinc-400 hover:text-white"
															onClick={() => moveSubject(subject, "up")}
															disabled={index === 0}
														>
															<ChevronUp className="size-4" />
														</Button>
														<Button
															variant="ghost"
															size="icon"
															className="h-6 w-6 text-zinc-400 hover:text-white"
															onClick={() => moveSubject(subject, "down")}
															disabled={index === subjectOrder.length - 1}
														>
															<ChevronDown className="size-4" />
														</Button>
													</div>
												</div>
												<Button
													variant="ghost"
													size="sm"
													onClick={() => addSection(subject)}
													className="text-purple-400 hover:text-purple-300"
												>
													<Plus className="size-4 mr-1" /> Add Section
												</Button>
											</div>
											<div className="grid gap-3">
												{Object.entries(subConfig.sections).map(
													([sectionName, secSettings]) => (
														<div
															key={sectionName}
															className="grid grid-cols-12 gap-2 items-end mb-2"
														>
															<div className="col-span-4">
																<Label className="text-xs text-zinc-500">
																	Section Name
																</Label>
																<Input
																	value={sectionName}
																	disabled
																	className="bg-zinc-950 border-white/10 h-8 text-sm"
																/>
															</div>
															<div className="col-span-3">
																<Label className="text-xs text-zinc-500">
																	Marks (+)
																</Label>
																<Input
																	type="number"
																	value={secSettings.marks}
																	onChange={(e) =>
																		handleSectionChange(
																			subject,
																			sectionName,
																			"marks",
																			e.target.value,
																		)
																	}
																	className="bg-zinc-950 border-white/10 h-8 text-sm"
																/>
															</div>
															<div className="col-span-3">
																<Label className="text-xs text-zinc-500">
																	Neg (-)
																</Label>
																<Input
																	type="number"
																	value={secSettings.negative_marks}
																	onChange={(e) =>
																		handleSectionChange(
																			subject,
																			sectionName,
																			"negative_marks",
																			e.target.value,
																		)
																	}
																	className="bg-zinc-950 border-white/10 h-8 text-sm"
																/>
															</div>
															<div className="col-span-3">
																<Label className="text-xs text-zinc-500">
																	Start Q
																</Label>
																<Input
																	type="number"
																	value={secSettings.start_q}
																	onChange={(e) =>
																		handleSectionChange(
																			subject,
																			sectionName,
																			"start_q",
																			e.target.value,
																		)
																	}
																	className="bg-zinc-950 border-white/10 h-8 text-sm"
																/>
															</div>
															<div className="col-span-3">
																<Label className="text-xs text-zinc-500">
																	End Q
																</Label>
																<Input
																	type="number"
																	value={secSettings.end_q}
																	onChange={(e) =>
																		handleSectionChange(
																			subject,
																			sectionName,
																			"end_q",
																			e.target.value,
																		)
																	}
																	className="bg-zinc-950 border-white/10 h-8 text-sm"
																/>
															</div>
															<div className="col-span-3">
																<Label className="text-xs text-zinc-500">
																	Type
																</Label>
																<select
																	value={secSettings.type}
																	onChange={(e) =>
																		handleSectionChange(
																			subject,
																			sectionName,
																			"type",
																			e.target.value,
																		)
																	}
																	className="w-full bg-zinc-950 border border-white/10 rounded h-8 text-sm text-white px-2"
																>
																	<option value="SCQ">SCQ</option>
																	<option value="MCQ">MCQ</option>
																	<option value="NUMERIC">NUMERIC</option>
																	<option value="INTEGER">INTEGER</option>
																</select>
															</div>
															<div className="col-span-12 flex justify-end mt-2">
																<Button
																	variant="ghost"
																	size="icon"
																	onClick={() =>
																		removeSection(subject, sectionName)
																	}
																	className="h-8 w-8 text-red-400 hover:bg-red-400/10"
																>
																	<Trash2 className="size-4" />
																</Button>
															</div>
														</div>
													),
												)}
											</div>
										</CardContent>
									</Card>
									);
								})}
							</div>
						</div>
					)}

					{step === "processing" && (
						<div className="flex flex-col items-center justify-center py-12 space-y-8 text-center">
							<div className="relative">
								<div className="absolute inset-0 bg-purple-500 blur-2xl opacity-20 animate-pulse" />
								{progress < 100 ? (
									<Loader2 className="size-16 text-purple-500 animate-spin relative z-10" />
								) : (
									<Brain className="size-16 text-purple-500 animate-pulse relative z-10" />
								)}
							</div>

							<div className="w-full max-w-md space-y-4">
								<div className="flex justify-between text-sm mb-1">
									<span className="text-purple-400 font-semibold">
										{statusMessage}
									</span>
									<span className="text-purple-300 tabular-nums">
										{progress}%
									</span>
								</div>
								<Progress
									value={progress}
									className="h-3 bg-zinc-800/50 border border-white/5"
									indicatorClassName="bg-gradient-to-r from-purple-600 to-purple-400 shadow-[0_0_10px_rgba(168,85,247,0.5)]"
								/>
								<p className="text-xs text-zinc-500 italic">
									{progress < 40 &&
										"Converting high-resolution images for AI analysis..."}
									{progress >= 40 &&
										progress < 80 &&
										"AI is reading questions and LaTeX formatting..."}
									{progress >= 80 &&
										progress < 100 &&
										"Finalizing test structure and solution mapping..."}
									{progress === 100 && "Ready! Finalizing test generation..."}
								</p>
							</div>

							<div className="bg-zinc-900/50 rounded-lg p-4 border border-white/5 max-w-sm">
								<p className="text-xs text-zinc-400 leading-relaxed">
									Our system is performing a deep scan of the PDF. This ensures
									100% accuracy in complex math and chemistry equations.
								</p>
							</div>
						</div>
					)}

					{step === "success" && parsingReport && (
						<div className="space-y-6 text-center py-6">
							<div className="mx-auto bg-green-500/10 p-4 rounded-full w-fit">
								<CheckCircle2 className="size-12 text-green-500" />
							</div>
							<div>
								<h3 className="text-2xl font-bold text-white">
									{parsingReport.report.is_symmetrical
										? "Test Generated Successfully!"
										: "Extraction Incomplete"}
								</h3>
								<p className="text-zinc-400">
									{parsingReport.report.is_symmetrical
										? "Your test is ready for review."
										: "Some questions were missing or duplicated. Check the report below."}
								</p>
							</div>

							{parsingReport.report.is_symmetrical === false && (
								<div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 flex items-start gap-3 text-left">
									<TriangleAlert className="size-5 text-amber-500 shrink-0 mt-0.5" />
									<div>
										<p className="text-amber-500 font-bold text-sm">
											Symmetry Warning
										</p>
										<p className="text-zinc-400 text-xs">
											{parsingReport.report.symmetry_message}
										</p>
									</div>
								</div>
							)}

							<div className="grid grid-cols-2 gap-4 text-left">
								<div className="bg-zinc-900 p-4 rounded-xl border border-white/10">
									<p className="text-zinc-500 text-sm">Total Extracted</p>
									<p className="text-2xl font-bold text-white">
										{parsingReport.report.total_extracted}
									</p>
								</div>
								<div className="bg-zinc-900 p-4 rounded-xl border border-white/10">
									<p className="text-zinc-500 text-sm">API Calls</p>
									<p className="text-2xl font-bold text-white">
										{parsingReport.report.api_calls}
									</p>
								</div>
							</div>

							<ScrollArea className="h-40 rounded-xl border border-white/10 bg-zinc-900/50 p-4 text-left">
								<pre className="text-xs text-zinc-300 font-mono">
									{JSON.stringify(parsingReport.report.subject_counts, null, 2)}
								</pre>
							</ScrollArea>
						</div>
					)}
				</div>

				<DialogFooter className="border-t border-white/10 pt-4">
					{step === "config" && (
						<>
							<Button variant="ghost" onClick={() => setStep("upload")}>
								Back
							</Button>
							<Button
								onClick={handleSubmit}
								className="bg-purple-600 hover:bg-purple-700 text-white"
							>
								Generate Test
							</Button>
						</>
					)}
					{step === "success" && (
						<Button
							onClick={() => {
								onClose();
								window.location.reload();
							}}
							className="w-full bg-green-600 hover:bg-green-700 text-white"
						>
							Close & View Test
						</Button>
					)}
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
